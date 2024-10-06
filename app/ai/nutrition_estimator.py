import os
import re
import json

from loguru import logger
import google.generativeai as genai

from app.models import Product
from app.ai.prompts import nutritional_info_estimation as nutrition_prompt


class NutritionEstimator:
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Please set the GEMINI_API_KEY environment variable")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-1.5-flash")

    def estimate_nutritional_info(self, product: Product) -> dict:
        prompt = f"{nutrition_prompt}\n\nProduct details:\nName: {product.name}\nDescription: {product.description}\nCategory: {product.category.name}"
        try:
            response = self.model.generate_content(prompt)
            json_str = response.candidates[0].content.parts[0].text
            # Extract the JSON object from the response text
            logger.debug(f"Response text: {json_str}")
            json_str = re.sub(r"^```json\s*\n", "", json_str)
            json_str = re.sub(r"\n\s*```$", "", json_str)
            nutritional_info = json.loads(json_str)
            logger.info(f"Information extracted: {nutritional_info}")
            return nutritional_info
        except Exception as e:
            logger.error(
                f"Error estimating nutritional information for product {product.id}: {str(e)}"
            )
            return {}


nutrition_estimator = NutritionEstimator()


def estimate_nutritional_info(product: Product) -> dict:
    return nutrition_estimator.estimate_nutritional_info(product)
