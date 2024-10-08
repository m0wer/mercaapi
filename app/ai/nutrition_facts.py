import requests
from loguru import logger
import os

from app.ai.prompts import nutritional_info
from app.ai.gemini import GeminiFileInformationExtractor
from app.models import TicketInfo


class NutritionFactsExtractor(GeminiFileInformationExtractor):
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash-latest"):
        super().__init__(api_key, model)
        self.prompt = nutritional_info

    def download_image(self, image_url: str) -> tuple[bytes, str]:
        logger.debug(f"Downloading image from {image_url}")
        response = requests.get(image_url)
        if response.status_code != 200:
            raise Exception(
                f"Failed to download image. Status code: {response.status_code}"
            )
        mime_type = response.headers.get("Content-Type", "image/jpeg")
        return response.content, mime_type

    async def extract_nutrition_facts(self, image_url: str) -> TicketInfo:
        image_data, mime_type = self.download_image(image_url)
        logger.info(f"Processing image URL: {image_url}")
        extract_info = await self.extract_ticket_info(image_data, mime_type)
        return extract_info


# Example usage
if __name__ == "__main__":
    api_key = os.environ.get("GEMINI_API_KEY")
    assert api_key, "Please set the GEMINI_API_KEY environment variable"
    image_url = "https://prod-mercadona.imgix.net/images/364c378b9cb83ffc2450203f335152b4.jpg?fit=crop&h=1600&w=1600"
    extractor = NutritionFactsExtractor(api_key)
    result = extractor.extract_nutrition_facts(image_url)
