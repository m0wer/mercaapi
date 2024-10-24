from datetime import datetime
from pathlib import Path
from typing import Union
import json
import re
import sys
import hashlib

import requests
from loguru import logger
from sh import ErrorReturnCode, ocrmypdf
from pymupdf.__main__ import main as fitz_command
from aiocache import Cache
from aiocache.serializers import JsonSerializer

from app.models import ExtractedTicketInfo, NutritionalInformation


class AIInformationExtractor:
    def __init__(
        self,
        groq_api_key: str,
        gemini_api_key: str,
        groq_model: str = "llama-3.1-70b-versatile",
        gemini_model: str = "gemini-1.5-flash-latest",
    ):
        # Groq configuration
        self.groq_api_key = groq_api_key
        self.groq_model = groq_model
        self.groq_base_url = "https://api.groq.com/openai/v1"
        self.groq_completion_url = f"{self.groq_base_url}/chat/completions"

        # Gemini configuration
        self.gemini_api_key = gemini_api_key
        self.gemini_model = gemini_model
        self.gemini_base_url = "https://generativelanguage.googleapis.com"
        self.upload_url = f"{self.gemini_base_url}/upload/v1beta/files"
        self.generate_url = (
            f"{self.gemini_base_url}/v1beta/models/{gemini_model}:generateContent"
        )

        # Initialize Redis cache with JSON serializer
        self.cache = Cache(
            Cache.REDIS,
            endpoint="redis",
            port=6379,
            serializer=JsonSerializer(),
            namespace="tickets",
        )

    def _calculate_file_hash(self, file_data: bytes) -> str:
        """Calculate SHA-256 hash of file contents."""
        return hashlib.sha256(file_data).hexdigest()

    async def process_file_ticket(
        self, file_path: Union[str, Path], prompt: str
    ) -> ExtractedTicketInfo:
        file_path = Path(file_path)

        # Read file contents for hashing
        with open(file_path, "rb") as f:
            file_data = f.read()

        file_hash = self._calculate_file_hash(file_data)
        cache_key = f"ticket:{file_hash}"

        # Try to get cached result
        cached_result = await self.cache.get(cache_key)
        if cached_result is not None:
            logger.info(f"Cache hit for file hash {file_hash}")
            return ExtractedTicketInfo.model_validate(cached_result)

        logger.info(f"Cache miss for file hash {file_hash}")

        # Process file based on type
        if file_path.suffix.lower() == ".pdf":
            text = await self._extract_text_from_pdf(file_path)
            result = self._extract_info_from_text(text, prompt)
        elif file_path.suffix.lower() in [".jpg", ".jpeg", ".png"]:
            result = await self._process_image_ticket(file_data, prompt)
        else:
            raise ValueError(
                "Unsupported file type. Please use PDF, JPEG, or PNG files."
            )

        # Convert ExtractedTicketInfo to dict before caching
        result_dict = result.model_dump()

        # Cache the result with a TTL of 24 hours (86400 seconds)
        await self.cache.set(cache_key, result_dict, ttl=86400)
        return result

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

    def _extract_info_from_text(self, text: str, prompt: str) -> ExtractedTicketInfo:
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json",
        }

        # Format messages for the chat completion
        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant that extracts structured information from text and returns it in JSON format. You will receive text content followed by specific extraction instructions. Always respond with valid JSON only, no additional text or markdown formatting.",
            },
            {
                "role": "user",
                "content": f"Here is the text to analyze:\n{text}\n\nExtraction instructions:\n{prompt}",
            },
        ]

        data = {
            "model": self.groq_model,
            "messages": messages,
            "temperature": 0.1,
            "stop": None,
        }

        logger.info("Extracting information from text using Groq")
        start = datetime.now()
        response = requests.post(self.groq_completion_url, headers=headers, json=data)
        logger.info(
            f"Request took {(datetime.now() - start).total_seconds():.3f} seconds"
        )

        if response.status_code == 200:
            try:
                response_data = response.json()
                json_str = response_data["choices"][0]["message"]["content"]

                # Clean up any potential markdown formatting
                json_str = re.sub(r"^```json\s*\n", "", json_str)
                json_str = re.sub(r"\n\s*```$", "", json_str)
                json_obj = json.loads(json_str)

                logger.info(f"Information extracted: {json_obj}")
                logger.debug(f"Usage statistics: {response_data.get('usage', {})}")

                if "items" in json_obj:
                    return ExtractedTicketInfo.model_validate(json_obj)
                else:
                    raise RuntimeError("No items found in the extracted JSON")
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Failed to parse JSON response: {e}")
                raise RuntimeError(f"Failed to parse response: {e}")
            except Exception as e:
                logger.error(f"Unhandled exception: {e}")
                raise
        else:
            logger.error(f"Error: {response.status_code}, {response.text}")
            raise Exception(f"Error: {response.status_code}, {response.text}")

    async def _process_image_ticket(
        self, file_data: bytes, prompt: str
    ) -> ExtractedTicketInfo:
        file_uri = self._upload_file(file_data, "image/jpeg")
        return self._extract_info_from_image(file_uri, prompt)

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
            f"{self.upload_url}?key={self.gemini_api_key}", headers=headers, data=data
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

    def _extract_info_from_image(
        self, file_uri: str, prompt: str
    ) -> ExtractedTicketInfo:
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
        logger.info(
            f"Extracting information using Gemini from image with URI: {file_uri}"
        )
        start = datetime.now()
        response = requests.post(
            f"{self.generate_url}?key={self.gemini_api_key}", headers=headers, json=data
        )
        logger.info(
            f"Request took {(datetime.now() - start).total_seconds():.3f} seconds"
        )

        if response.status_code == 200:
            logger.debug(f"Extract ticket AI response: {response.json()}")
            json_str = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            json_str = re.sub(r"^```json\s*\n", "", json_str)
            json_str = re.sub(r"\n\s*```$", "", json_str)
            json_obj = json.loads(json_str)
            logger.info(f"Information extracted: {json_obj}")

            if "items" in json_obj:
                return ExtractedTicketInfo.model_validate(json_obj)
            else:
                raise RuntimeError("No items found in the extracted JSON")
        else:
            logger.error(f"Error: {response.status_code}, {response.text}")
            raise Exception(f"Error: {response.status_code}, {response.text}")

    async def process_file_nutrition(
        self, file_path: Union[str, Path], prompt: str
    ) -> NutritionalInformation:
        file_path = Path(file_path)

        if file_path.suffix.lower() in [".jpg", ".jpeg", ".png"]:
            with open(file_path, "rb") as image_file:
                file_data = image_file.read()
            return await self._process_image_nutrition(file_data, prompt)
        else:
            raise ValueError("Unsupported file type. Please use JPEG, PNG files.")

    async def _process_image_nutrition(
        self, file_data: bytes, prompt: str
    ) -> NutritionalInformation:
        file_uri = self._upload_file(file_data, "image/jpeg")
        return self._extract_nutrition_info_from_file(file_uri, prompt)

    def _extract_nutrition_info_from_file(
        self, file_uri: str, prompt: str
    ) -> NutritionalInformation:
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
        logger.info(
            f"Extracting nutritional information using Gemini from file with URI: {file_uri}"
        )
        start = datetime.now()
        response = requests.post(
            f"{self.generate_url}?key={self.gemini_api_key}", headers=headers, json=data
        )
        logger.info(
            f"Request took {(datetime.now() - start).total_seconds():.3f} seconds"
        )

        if response.status_code == 200:
            json_str = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            json_str = re.sub(r"^```json\s*\n", "", json_str)
            json_str = re.sub(r"\n\s*```$", "", json_str)
            json_obj = json.loads(json_str)
            logger.info(f"Information extracted: {json_obj}")

            return NutritionalInformation.model_validate(json_obj)
        else:
            logger.error(f"Error: {response.status_code}, {response.text}")
            raise Exception(f"Error: {response.status_code}, {response.text}")
