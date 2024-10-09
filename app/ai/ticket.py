from pathlib import Path
from typing import Union
import json
import re
import sys

import requests
from loguru import logger
from sh import ErrorReturnCode, ocrmypdf
from pymupdf.__main__ import main as fitz_command

from app.models import TicketInfo, NutritionalInformation


class AIInformationExtractor:
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash-latest"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com"
        self.upload_url = f"{self.base_url}/upload/v1beta/files"
        self.generate_url = f"{self.base_url}/v1beta/models/{model}:generateContent"

    async def process_file(
        self, file_path: Union[str, Path], prompt: str
    ) -> Union[TicketInfo, NutritionalInformation]:
        file_path = Path(file_path)

        if file_path.suffix.lower() == ".pdf":
            text = await self._extract_text_from_pdf(file_path)
            return self._extract_info_from_text(text, prompt)
        elif file_path.suffix.lower() in [".jpg", ".jpeg", ".png"]:
            with open(file_path, "rb") as image_file:
                file_data = image_file.read()
            return await self._process_image(file_data, prompt)
        else:
            raise ValueError(
                "Unsupported file type. Please use PDF, JPEG, or PNG files."
            )

    async def _extract_text_from_pdf(self, file_path: Path) -> str:
        try:
            ocrmypdf("--skip-text", str(file_path), str(file_path))
        except ErrorReturnCode as e:
            logger.warning(f"OCR failed for {file_path}: {e}")

        sys.argv[1:] = [
            "gettext",
            "-mode",
            "layout",
            str(file_path),
            "-output",
            str(file_path.with_suffix(".txt")),
        ]

        try:
            fitz_command()
        except SystemExit as e:
            logger.error(f"fitz command failed for {file_path}: {e}")
            return ""

        try:
            with open(file_path.with_suffix(".txt"), "r") as f:
                text = f.read()
        except UnicodeDecodeError:
            logger.warning(f"Could not decode {file_path}")
            return ""

        return " ".join(filter(None, text.split(" ")))[:4000]

    def _extract_info_from_text(
        self, text: str, prompt: str
    ) -> Union[TicketInfo, NutritionalInformation]:
        headers = {"Content-Type": "application/json"}
        data = {
            "contents": [
                {
                    "parts": [
                        {"text": text},
                        {"text": prompt},
                    ]
                }
            ]
        }
        logger.info("Extracting information from text")
        response = requests.post(
            f"{self.generate_url}?key={self.api_key}", headers=headers, json=data
        )

        if response.status_code == 200:
            json_str = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            json_str = re.sub(r"^```json\s*\n", "", json_str)
            json_str = re.sub(r"\n\s*```$", "", json_str)
            json_obj = json.loads(json_str)
            logger.info(f"Information extracted: {json_obj}")

            if "items" in json_obj:
                return TicketInfo.parse_obj(json_obj)
            else:
                return NutritionalInformation.parse_obj(json_obj)
        else:
            logger.error(f"Error: {response.status_code}, {response.text}")
            raise Exception(f"Error: {response.status_code}, {response.text}")

    async def _process_image(
        self, file_data: bytes, prompt: str
    ) -> Union[TicketInfo, NutritionalInformation]:
        file_uri = self._upload_file(file_data, "image/jpeg")
        return self._extract_info_from_file(file_uri, prompt)

    def _upload_file(self, file_data: bytes, mime_type: str) -> str:
        num_bytes = len(file_data)
        display_name = "IMAGE"

        headers = {
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(num_bytes),
            "X-Goog-Upload-Header-Content-Type": mime_type,
            "Content-Type": "application/json",
        }
        data = json.dumps({"file": {"display_name": display_name}})
        response = requests.post(
            f"{self.upload_url}?key={self.api_key}", headers=headers, data=data
        )
        if response.status_code != 200:
            raise Exception(
                f"Failed to initiate upload. Status code: {response.status_code}"
            )
        upload_url = response.headers["X-Goog-Upload-URL"]

        headers = {
            "Content-Length": str(num_bytes),
            "X-Goog-Upload-Offset": "0",
            "X-Goog-Upload-Command": "upload, finalize",
        }
        response = requests.post(upload_url, headers=headers, data=file_data)
        if response.status_code != 200:
            raise Exception(
                f"Failed to upload file. Status code: {response.status_code}"
            )
        file_info = response.json()
        return file_info["file"]["uri"]

    def _extract_info_from_file(
        self, file_uri: str, prompt: str
    ) -> Union[TicketInfo, NutritionalInformation]:
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
                            "text": prompt,
                        },
                    ]
                }
            ]
        }
        logger.info(f"Extracting information from file with URI: {file_uri}")
        response = requests.post(
            f"{self.generate_url}?key={self.api_key}", headers=headers, json=data
        )

        if response.status_code == 200:
            json_str = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            json_str = re.sub(r"^```json\s*\n", "", json_str)
            json_str = re.sub(r"\n\s*```$", "", json_str)
            json_obj = json.loads(json_str)
            logger.info(f"Information extracted: {json_obj}")

            if "items" in json_obj:
                return TicketInfo.parse_obj(json_obj)
            else:
                return NutritionalInformation.parse_obj(json_obj)
        else:
            logger.error(f"Error: {response.status_code}, {response.text}")
            raise Exception(f"Error: {response.status_code}, {response.text}")


# Usage example
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key is None:
        raise ValueError("GEMINI_API_KEY key not found in environment variables")
    extractor = AIInformationExtractor(api_key)

    # Example for processing a ticket image
    ticket_prompt = """
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
    ticket_info = extractor.process_file("path/to/ticket.jpg", ticket_prompt)
    print(ticket_info)

    # Example for processing a nutrition facts image
    nutrition_prompt = """
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
    nutrition_info = extractor.process_file("path/to/nutrition.png", nutrition_prompt)
    print(nutrition_info)
