import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlmodel import Session
from loguru import logger
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Union, Optional
import requests

from app.database import get_session
from app.models import (
    TicketStats,
    TicketItem,
    ItemStats,
    ExtractedTicketInfo,
    ProductPublic,
)
from app.shared.cache import get_all_products
from app.shared.product_matcher import find_closest_products
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


def calculate_item_stats(
    product: ProductPublic, quantity: int, total_price: float
) -> Optional[ItemStats]:
    if product.nutritional_information is None:
        return None

    ni = product.nutritional_information
    unit_size = product.unit_size if product.unit_size is not None else 1
    total_weight = unit_size * quantity

    calories = (ni.calories or 0) * total_weight / 100
    proteins = (ni.protein or 0) * total_weight / 100
    carbs = (ni.total_carbohydrate or 0) * total_weight / 100
    fat = (ni.total_fat or 0) * total_weight / 100
    fiber = (ni.dietary_fiber or 0) * total_weight / 100

    daily_kcal = 2000  # Default value, can be made configurable

    return ItemStats(
        calories=calories,
        proteins=proteins,
        carbs=carbs,
        fat=fat,
        fiber=fiber,
        cost_per_daily_kcal=(total_price / calories) * daily_kcal
        if calories > 0
        else None,
        cost_per_100g_protein=(total_price / proteins) * 100 if proteins > 0 else None,
        cost_per_100g_carb=(total_price / carbs) * 100 if carbs > 0 else None,
        cost_per_100g_fat=(total_price / fat) * 100 if fat > 0 else None,
        kcal_per_euro=calories / total_price if total_price > 0 else None,
    )


@router.post("/", response_model=TicketStats)
async def process_ticket_and_calculate_stats(
    file: Union[UploadFile, None] = File(None),
    image_url: Union[str, None] = Form(None),
    session: Session = Depends(get_session),
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

            ticket_info: ExtractedTicketInfo = await extractor.process_file_ticket(
                temp_file_path, TICKET_PROMPT
            )

        all_products = get_all_products(session)
        ticket_items = []

        for item in ticket_info.items:
            closest_products = find_closest_products(
                all_products, item.name, item.unit_price
            )

            if not closest_products:
                logger.warning(f"No match found for product '{item.name}'.")
                continue

            product = closest_products[0].product
            logger.info(
                f"Best match for '{item.name}': {product.name} (Score: {closest_products[0].score:.2f})"
            )

            item_stats = calculate_item_stats(
                product, item.quantity, item.total_price or 0
            )

            ticket_item = TicketItem(
                product=ProductPublic.model_validate(product),
                original_name=item.name,
                quantity=item.quantity,
                unit_price=item.unit_price or 0,
                total_price=item.total_price or 0,
                stats=item_stats,
            )
            ticket_items.append(ticket_item)

        return TicketStats(items=ticket_items)

    except Exception as e:
        logger.error(f"Error processing ticket: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error processing ticket: {str(e)}"
        )


@router.post("/", response_model=TicketStats)
async def process_ticket(
    file: Union[UploadFile, None] = File(None),
    image_url: Union[str, None] = Form(None),
    session: Session = Depends(get_session),
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

            ticket_info: ExtractedTicketInfo = await extractor.process_file_ticket(
                temp_file_path, TICKET_PROMPT
            )

        all_products = get_all_products(session)
        ticket_items = []

        for item in ticket_info.items:
            closest_products = find_closest_products(
                all_products, item.name, item.unit_price
            )

            if not closest_products:
                logger.warning(f"No match found for product '{item.name}'.")
                continue

            product = closest_products[0].product
            logger.info(
                f"Best match for '{item.name}': {product.name} (Score: {closest_products[0].score:.2f})"
            )

            item_stats = calculate_item_stats(
                product, item.quantity, item.total_price or 0
            )

            ticket_item = TicketItem(
                product=ProductPublic.model_validate(product),
                original_name=item.name,
                quantity=item.quantity,
                unit_price=item.unit_price or 0,
                total_price=item.total_price or 0,
                stats=item_stats,
            )
            ticket_items.append(ticket_item)

        return TicketStats(items=ticket_items)

    except Exception as e:
        logger.error(f"Error processing ticket: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error processing ticket: {str(e)}"
        )
