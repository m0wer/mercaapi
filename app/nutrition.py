import os
import json
import requests
import loguru
import re
from typing import Dict, Any


class GeminiNutritionalFactsExtractor:
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash-latest"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com"
        self.upload_url = f"{self.base_url}/upload/v1beta/files"
        self.generate_url = f"{self.base_url}/v1beta/models/{model}:generateContent"

    def upload_image(self, image_url: str) -> str:
        # Download the image
        loguru.logger.debug(f"Downloading image from {image_url}")
        response = requests.get(image_url)
        if response.status_code != 200:
            raise Exception(
                f"Failed to download image. Status code: {response.status_code}"
            )
        image_data = response.content
        # Get image metadata
        mime_type = response.headers.get("Content-Type", "image/jpeg")
        num_bytes = len(image_data)
        display_name = "TEXT"

        # Initial resumable request defining metadata
        headers = {
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(num_bytes),
            "X-Goog-Upload-Header-Content-Type": mime_type,
            "Content-Type": "application/json",
        }
        data = json.dumps({"file": {"display_name": display_name}})
        loguru.logger.debug(f"Initiating image upload with metadata: {data}")
        response = requests.post(
            f"{self.upload_url}?key={self.api_key}", headers=headers, data=data
        )
        if response.status_code != 200:
            raise Exception(
                f"Failed to initiate upload. Status code: {response.status_code}"
            )
        upload_url = response.headers["X-Goog-Upload-URL"]
        loguru.logger.debug(f"Upload URL: {upload_url}")

        # Upload the actual bytes
        headers = {
            "Content-Length": str(num_bytes),
            "X-Goog-Upload-Offset": "0",
            "X-Goog-Upload-Command": "upload, finalize",
        }
        loguru.logger.debug("Uploading image data")
        response = requests.post(upload_url, headers=headers, data=image_data)
        if response.status_code != 200:
            raise Exception(
                f"Failed to upload image. Status code: {response.status_code}"
            )
        file_info = response.json()
        loguru.logger.debug(f"Upload successful. File info: {file_info}")
        return file_info["file"]["uri"]

    def extract_info_from_image_uri(self, file_uri: str) -> Dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        data = {
            "contents": [
                {
                    "parts": [
                        {
                            "file_data": {
                                "mime_type": "image/jpeg",
                                "file_uri": file_uri,
                            }
                        },
                        {
                            "text": """
                    Extract all nutritional information from this image. 
                    Provide the output as a JSON object with the following structure:
                    {
                        "calories_kJ": number,
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
                    Use null for any values not present in the image.
                    Ensure all numeric values are numbers, not strings.
                    """
                        },
                    ]
                }
            ]
        }
        loguru.logger.info(
            f"Extracting nutritional information from image with URI: {file_uri}"
        )
        response = requests.post(
            f"{self.generate_url}?key={self.api_key}", headers=headers, json=data
        )

        if response.status_code == 200:
            json_str = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            # Extract the JSON object from the response text
            loguru.logger.debug(f"Response text: {json_str}")
            json_str = re.sub(r"^```json\s*\n", "", json_str)
            json_str = re.sub(r"\n\s*```$", "", json_str)
            json_obj = json.loads(json_str)
            loguru.logger.info(f"Nutritional information extracted: {json_obj}")
            return json_obj
        else:
            loguru.logger.error(f"Error: {response.status_code}, {response.text}")
            raise Exception(f"Error: {response.status_code}, {response.text}")

    def process_image_url(self, image_url: str) -> dict:
        loguru.logger.info(f"Processing image URL: {image_url}")
        file_uri = self.upload_image(image_url)
        nutritional_info = self.extract_info_from_image_uri(file_uri)
        del nutritional_info["calories_jK"]
        nutritional_info["calories"] = nutritional_info.pop("calories_kcal")
        return nutritional_info


# Example usage
if __name__ == "__main__":
    api_key = os.environ.get("GEMINI_API_KEY")
    assert api_key, "Please set the GEMINI_API_KEY environment variable"
    # image_url = "https://prod-mercadona.imgix.net/images/35fb9cb075a4ddd11ddf9eaf7a20dcc2.jpg?fit=crop&h=1600&w=1600"
    # image_url = "https://prod-mercadona.imgix.net/images/602715e9a771a9d98e6b26dae428572e.jpg?fit=crop&h=1600&w=1600"
    # image_url = "https://prod-mercadona.imgix.net/images/095dffa8053fb32c2c81a774a1aa1516.jpg?fit=crop&h=1600&w=1600"
    # image_url = "https://prod-mercadona.imgix.net/images/e9094a9837bad1b646cafa08476dcc32.jpg?fit=crop&h=600&w=600"
    # image_url = "https://prod-mercadona.imgix.net/images/9e525520b7c03aed08536ea31877293d.jpg?fit=crop&h=1600&w=1600"
    image_url = "https://prod-mercadona.imgix.net/images/364c378b9cb83ffc2450203f335152b4.jpg?fit=crop&h=1600&w=1600"
    extractor = GeminiNutritionalFactsExtractor(api_key)
    result = extractor.process_image_url(image_url)
