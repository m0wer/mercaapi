import json
import requests
import re
from typing import Union
from pathlib import Path
import sys
import time

from loguru import logger
import aiofiles
from sh import ErrorReturnCode, ocrmypdf
from pymupdf.__main__ import main as fitz_command

from app.models import TicketInfo


class GeminiFileInformationExtractor:
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash-latest"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com"
        self.generate_url = f"{self.base_url}/v1beta/models/{model}:generateContent"
        self.prompt = """
        Extract all products/items from this text.
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
        Use null for any values not present in the text.
        Ensure all numeric values are numbers, not strings.

        The ticket text comes from a PDF file with several pages.
        There's one product per line excpet for line with weight information for products sold by weight one line above).
        Ignore the lines that have "Peso", they are not products.

        The columns are product name, quantity, and total prics (unit price * quantity).
        For porducts that are sold by weight,
        there's a line below the prorduct name with the weigth and price per kilogram.
        """

    async def extract_text_from_pdf(self, file_path: Path) -> str:
        try:
            ocrmypdf("--skip-text", str(file_path), str(file_path))
        except ErrorReturnCode as e:
            logger.warning(f"OCR failed for {file_path}: {e}")

        saved_parms = sys.argv[1:]
        sys.argv[1:] = [
            "gettext",
            "-mode",
            "layout",
            str(file_path),
            "-output",
            str(file_path.with_suffix(".txt")),
        ]

        logger.debug("Starting fitz command")
        start = time.time()
        try:
            fitz_command()
        except SystemExit as e:
            logger.error(f"fitz command failed for {file_path}: {e}")
            return ""
        end = time.time()
        logger.debug(f"Finished fitz command in {end - start:.3f} seconds")

        sys.argv[1:] = saved_parms

        async with aiofiles.open(file_path.with_suffix(".txt"), "r") as f:
            try:
                text = await f.read()
            except UnicodeDecodeError:
                logger.warning(f"Could not decode {file_path}")
                return ""

        return " ".join(filter(None, text.split(" ")))[:4000]

    def extract_info_from_text(self, text: str) -> TicketInfo:
        headers = {"Content-Type": "application/json"}
        data = {
            "contents": [
                {
                    "parts": [
                        {"text": text},
                        {"text": self.prompt},
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
            return TicketInfo.parse_obj(json_obj)
        else:
            logger.error(f"Error: {response.status_code}, {response.text}")
            raise Exception(f"Error: {response.status_code}, {response.text}")

    async def process_file(self, file_path: Union[str, Path]) -> TicketInfo:
        file_path = Path(file_path)

        if file_path.suffix.lower() == ".pdf":
            text = await self.extract_text_from_pdf(file_path)
        elif file_path.suffix.lower() in [".jpg", ".jpeg", ".png"]:
            with open(file_path, "rb") as image_file:
                text = image_file.read().decode("utf-8", errors="ignore")
        else:
            raise ValueError(
                "Unsupported file type. Please use PDF, JPEG, or PNG files."
            )

        return self.extract_info_from_text(text)

    async def extract_ticket_info(self, file_data: bytes, mime_type: str) -> TicketInfo:
        logger.info("Processing ticket from bytes")
        try:
            temp_file = Path(
                f"temp_file{'.pdf' if mime_type == 'application/pdf' else '.jpg'}"
            )
            with open(temp_file, "wb") as f:
                f.write(file_data)

            extract_info = await self.process_file(temp_file)
            temp_file.unlink()  # Remove the temporary file
            return extract_info

        except Exception as e:
            logger.error(f"Error in extract_ticket_info: {str(e)}")
            raise
