import os

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlmodel import Session
from pydantic import BaseModel, model_validator
from loguru import logger

from app.database import get_session
from app.models import Product
from app.ai.ticket import TicketImageInformationExtractor
from app.shared.cache import get_all_products
from app.shared.product_matcher import find_closest_products

router = APIRouter(prefix="/ticket", tags=["ticket"])


class TicketItem(BaseModel):
    name: str
    quantity: int = 1
    total_price: float | None = None
    unit_price: float | None = None

    @model_validator(mode="before")
    @classmethod
    def guess_unit_price(cls, data: dict):
        if "unit_price" not in data or data["unit_price"] is None:
            if (
                "total_price" in data
                and data["total_price"] is not None
                and data["total_price"] != 0
                and data["quantity"] != 0
            ):
                data["unit_price"] = data["total_price"] / data["quantity"]
        return data


class TicketInfo(BaseModel):
    ticket_number: int | None = None
    date: str | None = None
    time: str | None = None
    total_price: float | None = None
    items: list[TicketItem]


class ProductInfo(BaseModel):
    product: Product
    is_food: bool
    total_weight: float | None = None
    total_calories: float | None = None
    total_protein: float | None = None
    total_carbs: float | None = None
    total_fat: float | None = None


class TicketStats(BaseModel):
    total_calories: float
    total_proteins: float
    total_carbs: float
    total_fat: float
    total_fiber: float
    avg_cost_per_daily_kcal: float
    avg_cost_per_100g_protein: float
    avg_cost_per_100g_carb: float
    avg_cost_per_100g_fat: float
    kcal_per_euro: float
    number_of_daily_doses: float
    average_daily_cost: float
    protein_ratio: float
    carb_ratio: float
    fat_ratio: float
    food_percentage: float
    total_food_amount: float
    food_products: list[ProductInfo]
    non_food_products: list[ProductInfo]


@router.post("/")
async def process_ticket(file: UploadFile = File(...)):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="API key not configured")

    extractor = TicketImageInformationExtractor(api_key=api_key)
    file_data = await file.read()
    mime_type = file.content_type

    try:
        extract_info = extractor.extract_ticket_info(file_data, mime_type)
    except Exception as e:
        logger.error(f"Error extracting ticket information: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to extract ticket information"
        )
    return extract_info


def calculate_total(
    amount_per_100_g: float | None = None,
    quantity: int = 1,
    unit_name: str | None = None,
    unit_size: float | None = None,
):
    if amount_per_100_g is None:
        return None

    if unit_name is None:
        return 10 * amount_per_100_g * quantity
    else:
        logger.warning(f"Unable to calculate total for unit_name: {unit_name}")
        return None


@router.post("/stats")
async def calculate_ticket_stats(
    ticket_info: TicketInfo,
    daily_kcal: int = Query(default=2000, ge=1000, le=5000),
    session: Session = Depends(get_session),
):
    total_calories = 0
    total_proteins = 0
    total_carbs = 0
    total_fat = 0
    total_fiber = 0
    total_food_price: float = 0.0
    food_products = []
    non_food_products = []

    all_products = get_all_products(session)

    for item in ticket_info.items:
        closest_products = find_closest_products(
            all_products, item.name, item.unit_price
        )

        if not closest_products:
            logger.warning(f"No match found for product '{item.name}'.")
            non_food_products.append(
                ProductInfo(
                    product=Product(name=item.name, price=item.unit_price),
                    is_food=False,
                )
            )
            continue

        product = closest_products[0].product
        logger.info(
            f"Best match for '{item.name}': {product.name} (Score: {closest_products[0].score:.2f})"
        )

        is_food = (
            product.nutritional_information is not None
            and product.nutritional_information.calories is not None
        )
        product_info = ProductInfo(product=product, is_food=is_food)

        if is_food and product.nutritional_information:
            unit_size = product.unit_size if product.unit_size is not None else 1

            calories = calculate_total(
                product.nutritional_information.calories,
                item.quantity,
                product.unit_name,
                unit_size,
            )
            proteins = calculate_total(
                product.nutritional_information.protein,
                item.quantity,
                product.unit_name,
                unit_size,
            )
            carbs = calculate_total(
                product.nutritional_information.total_sugars,
                item.quantity,
                product.unit_name,
                unit_size,
            )
            fats = calculate_total(
                product.nutritional_information.total_fat,
                item.quantity,
                product.unit_name,
                unit_size,
            )
            fiber = calculate_total(
                product.nutritional_information.dietary_fiber,
                item.quantity,
                product.unit_name,
                unit_size,
            )

            if calories is not None:
                total_calories += calories
                total_food_price += item.total_price or 0.0
                product_info.total_calories = int(calories)
                product_info.total_weight = unit_size * item.quantity
                product_info.total_protein = proteins
                product_info.total_carbs = carbs
                product_info.total_fat = fats

            if proteins is not None:
                total_proteins += proteins
            if carbs is not None:
                total_carbs += carbs
            if fats is not None:
                total_fat += fats
            if fiber is not None:
                total_fiber += fiber

            food_products.append(product_info)

            logger.debug(
                f"Product: {product.name}, Calories: {calories}, Protein: {proteins}, Carbs: {carbs}, Fat: {fats}, Fiber: {fiber}"
            )
        else:
            non_food_products.append(product_info)

    total_price: float = ticket_info.total_price or sum(
        item.total_price for item in ticket_info.items if item.total_price is not None
    )
    food_percentage = (total_food_price / total_price) * 100 if total_price > 0 else 0

    if total_calories == 0:
        logger.warning(
            "No food products found in the ticket. Unable to calculate nutritional stats."
        )
        return None

    avg_cost_per_daily_kcal = (total_food_price / total_calories) * daily_kcal
    avg_cost_per_100g_protein = (
        (total_food_price / total_proteins) * 100 if total_proteins > 0 else 0
    )
    avg_cost_per_100g_carb = (
        (total_food_price / total_carbs) * 100 if total_carbs > 0 else 0
    )
    avg_cost_per_100g_fat = (total_food_price / total_fat) * 100 if total_fat > 0 else 0
    kcal_per_euro = total_calories / total_food_price
    number_of_daily_doses = total_calories / daily_kcal
    average_daily_cost = total_food_price / number_of_daily_doses

    total_macros = total_proteins + total_carbs + total_fat
    protein_ratio = (total_proteins / total_macros) * 100 if total_macros > 0 else 0
    carb_ratio = (total_carbs / total_macros) * 100 if total_macros > 0 else 0
    fat_ratio = (total_fat / total_macros) * 100 if total_macros > 0 else 0

    return TicketStats(
        total_calories=total_calories,
        total_proteins=total_proteins,
        total_carbs=total_carbs,
        total_fat=total_fat,
        total_fiber=total_fiber,
        avg_cost_per_daily_kcal=avg_cost_per_daily_kcal,
        avg_cost_per_100g_protein=avg_cost_per_100g_protein,
        avg_cost_per_100g_carb=avg_cost_per_100g_carb,
        avg_cost_per_100g_fat=avg_cost_per_100g_fat,
        kcal_per_euro=kcal_per_euro,
        number_of_daily_doses=number_of_daily_doses,
        average_daily_cost=average_daily_cost,
        protein_ratio=protein_ratio,
        carb_ratio=carb_ratio,
        fat_ratio=fat_ratio,
        food_percentage=food_percentage,
        total_food_amount=total_food_price,
        food_products=food_products,
        non_food_products=non_food_products,
    )
