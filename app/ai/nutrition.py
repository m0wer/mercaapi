"""Nutrition facts extraction, estimation, and validation.

Extraction uses a vision-capable model on the product images (all images in a
single request, the model picks the nutrition table if present). When no
nutrition table is visible, values are estimated from the product name,
description, and category. All values are per 100 g (or 100 ml) and validated
before being stored.
"""

from typing import Any

from loguru import logger
from pydantic import BaseModel, field_validator

from app.ai.client import AIClient, AIClientError, image_content_from_url
from app.models import Product

# Physiological bounds for values per 100 g.
MAX_KCAL_PER_100G = 950  # pure fat is ~900 kcal/100 g
MAX_GRAMS_PER_100G = 100
KJ_PER_KCAL = 4.184

MACRO_FIELDS = (
    "total_fat",
    "saturated_fat",
    "polyunsaturated_fat",
    "monounsaturated_fat",
    "trans_fat",
    "total_carbohydrate",
    "dietary_fiber",
    "total_sugars",
    "protein",
    "salt",
)

NUTRITION_JSON_FORMAT = """
Provide the output as a JSON object with the following structure:
{
    "calories_kj": number,
    "calories_kcal": number,
    "total_fat": number,
    "saturated_fat": number,
    "polyunsaturated_fat": number,
    "monounsaturated_fat": number,
    "trans_fat": number,
    "total_carbohydrate": number,
    "dietary_fiber": number,
    "total_sugars": number,
    "protein": number,
    "salt": number
}
All values must be per 100 grams (or 100 ml for liquids).
Use null for any value that is not available.
Ensure all numeric values are numbers, not strings. Use dots for decimals.
Respond with the JSON object only, no additional text or markdown.
"""

EXTRACTION_PROMPT = (
    "You are given photos of a food product sold in a Spanish supermarket. "
    "Find the nutrition facts table (tabla de informacion nutricional) in the "
    "images and extract the values per 100 g or 100 ml. "
    "If no nutrition table is visible in any image, return null for every "
    "field.\n" + NUTRITION_JSON_FORMAT
)

ESTIMATION_PROMPT = (
    "Estimate typical nutritional values per 100 grams for the following "
    "Spanish supermarket food product. Base the estimate on well-known "
    "nutritional data for this kind of product.\n" + NUTRITION_JSON_FORMAT
)


class NutritionFacts(BaseModel):
    """Nutrition values per 100 g as returned by the AI, before cleaning."""

    calories_kj: float | None = None
    calories_kcal: float | None = None
    total_fat: float | None = None
    saturated_fat: float | None = None
    polyunsaturated_fat: float | None = None
    monounsaturated_fat: float | None = None
    trans_fat: float | None = None
    total_carbohydrate: float | None = None
    dietary_fiber: float | None = None
    total_sugars: float | None = None
    protein: float | None = None
    salt: float | None = None

    @field_validator("*", mode="before")
    @classmethod
    def coerce_number(cls, value: Any) -> Any:
        """Coerce values like "12,5", "1.2 g" or "<0.5" to floats."""
        if value is None or isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            cleaned = value.strip().replace(",", ".")
            cleaned = "".join(c for c in cleaned if c.isdigit() or c == ".")
            if not cleaned or cleaned == ".":
                return None
            try:
                return float(cleaned)
            except ValueError:
                return None
        return None


def clean_nutrition_facts(facts: NutritionFacts) -> dict[str, float | None] | None:
    """Validate and normalize nutrition facts to database column values.

    Returns a dict with the ``NutritionalInformation`` column values (using
    ``calories`` in kcal), or ``None`` when there is no usable data.
    """
    calories = facts.calories_kcal
    # Recover kcal from kJ when kcal is missing or the two were swapped.
    if calories is None and facts.calories_kj is not None:
        calories = facts.calories_kj / KJ_PER_KCAL
    elif calories is not None and calories > MAX_KCAL_PER_100G:
        # Value was likely reported in kJ.
        converted = calories / KJ_PER_KCAL
        calories = converted if converted <= MAX_KCAL_PER_100G else None

    if calories is not None:
        if calories < 0:
            calories = None
        else:
            calories = round(calories, 1)

    values: dict[str, float | None] = {"calories": calories}
    for field in MACRO_FIELDS:
        value = getattr(facts, field)
        if value is not None and not 0 <= value <= MAX_GRAMS_PER_100G:
            value = None
        values[field] = round(value, 2) if value is not None else None

    if all(value is None for value in values.values()):
        return None
    return values


def is_plausible_nutrition(values: dict[str, Any]) -> bool:
    """Check whether stored nutrition values are physiologically plausible."""
    calories = values.get("calories")
    if calories is not None and not 0 <= calories <= MAX_KCAL_PER_100G:
        return False

    for field in MACRO_FIELDS:
        value = values.get(field)
        if value is not None and not 0 <= value <= MAX_GRAMS_PER_100G:
            return False

    fat = values.get("total_fat")
    carbs = values.get("total_carbohydrate")
    protein = values.get("protein")
    macros = [value for value in (fat, carbs, protein) if value is not None]
    if sum(macros) > 105:
        return False

    # Calories should roughly match the Atwater estimate from macros.
    if calories is not None and len(macros) == 3:
        estimated = 9 * (fat or 0) + 4 * (carbs or 0) + 4 * (protein or 0)
        if estimated > 100 and calories < estimated * 0.4:
            return False
        if calories > 100 and calories > estimated * 2.5 + 100:
            return False

    return True


class NutritionAI:
    """High-level nutrition extraction and estimation using an AI client."""

    def __init__(self, client: AIClient | None = None):
        self.client = client or AIClient()

    def extract_from_images(
        self, image_urls: list[str]
    ) -> dict[str, float | None] | None:
        """Extract nutrition facts from product images (single AI call)."""
        if not image_urls:
            return None
        content: list[dict[str, Any]] = [
            {"type": "text", "text": EXTRACTION_PROMPT}
        ]
        content.extend(image_content_from_url(url) for url in image_urls)
        try:
            raw = self.client.complete_json([{"role": "user", "content": content}])
        except AIClientError as e:
            logger.error(f"Nutrition extraction from images failed: {e}")
            return None
        return clean_nutrition_facts(NutritionFacts.model_validate(raw))

    def estimate_from_product(
        self, product: Product
    ) -> dict[str, float | None] | None:
        """Estimate nutrition facts from product name/description/category."""
        details = f"Name: {product.name}"
        if product.brand:
            details += f"\nBrand: {product.brand}"
        if product.description:
            details += f"\nDescription: {product.description}"
        if product.category:
            details += f"\nCategory: {product.category.name}"
        try:
            raw = self.client.complete_json(
                [
                    {
                        "role": "user",
                        "content": f"{ESTIMATION_PROMPT}\nProduct details:\n{details}",
                    }
                ]
            )
        except AIClientError as e:
            logger.error(f"Nutrition estimation failed for {product.id}: {e}")
            return None
        return clean_nutrition_facts(NutritionFacts.model_validate(raw))

    def get_nutrition_for_product(
        self, product: Product
    ) -> dict[str, float | None] | None:
        """Extract nutrition from images, falling back to estimation."""
        image_urls = [image.zoom_url for image in product.images]
        values = self.extract_from_images(image_urls)
        if values is not None and values.get("calories") is not None:
            logger.info(f"Extracted nutrition from images for product {product.id}")
            return values
        logger.info(
            f"No nutrition table found in images for product {product.id}, "
            "estimating from product details"
        )
        return self.estimate_from_product(product)
