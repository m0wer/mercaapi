import os

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlmodel import Session
from loguru import logger
from pathlib import Path

from app.database import get_session
from app.models import Product, TicketStats, TicketInfo, ProductInfo
from app.shared.cache import get_all_products
from app.shared.product_matcher import find_closest_products
from tempfile import TemporaryDirectory
from typing import Union

from fastapi import Form
import requests

from app.ai.ticket import AIInformationExtractor

router = APIRouter(prefix="/ticket", tags=["ticket"])

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY environment variable is not set")

extractor = AIInformationExtractor(api_key=api_key)

TICKET_PROMPT = """
Extract all products/items from this image.
Provide the output as a JSON object with the following structure:
{
    "ticket_number": number,
    "date": "DD/MM/YYYY",
    "time": "HH:MM",
    "total_price": number,
    "items": [
        {
            "name": "string",
            "quantity": number,
            "total_price": number,
            "unit_price": number
        }
    ]
}
Use null for any values not present in the image.
Ensure all numeric values are numbers, not strings.
"""


@router.post("/", response_model=TicketInfo)
async def process_ticket(
    file: Union[UploadFile, None] = File(None), image_url: Union[str, None] = Form(None)
):
    if file is None and image_url is None:
        raise HTTPException(
            status_code=400, detail="Either file or image_url must be provided"
        )

    try:
        with TemporaryDirectory() as temp_dir:
            if file:
                temp_file_path = Path(temp_dir) / file.filename
                with temp_file_path.open("wb") as buffer:
                    buffer.write(await file.read())
            elif image_url:
                response = requests.get(image_url)
                response.raise_for_status()
                temp_file_path = Path(temp_dir) / "image_from_url"
                temp_file_path.write_bytes(response.content)

            ticket_info = await extractor.process_file(temp_file_path, TICKET_PROMPT)

        return ticket_info
    except Exception as e:
        logger.error(f"Error processing ticket: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error processing ticket: {str(e)}"
        )


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
