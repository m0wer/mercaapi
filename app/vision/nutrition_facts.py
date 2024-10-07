import requests
from loguru import logger

from app.vision.prompts import nutritional_info
from app.vision.gemini import GeminiImageInformationExtractor


class NutritionFactsExtractor(GeminiImageInformationExtractor):
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

    def extract_nutrition_facts(self, image_url: str) -> dict:
        image_data, mime_type = self.download_image(image_url)
        logger.info(f"Processing image URL: {image_url}")
        files = self.upload_files([(image_data, mime_type)])
        extract_info = self.extract_info_from_files(files, self.prompt)
        return extract_info
