from pathlib import Path
from typing import Any, Union
import hashlib
import os
import sys

from loguru import logger
from sh import ErrorReturnCode, ocrmypdf
from pymupdf.__main__ import main as fitz_command
from aiocache import Cache
from aiocache.serializers import JsonSerializer

from app.ai.client import AIClient, image_content_from_bytes
from app.models import ExtractedTicketInfo

MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


class AIInformationExtractor:
    """Extract structured ticket information from PDFs and images."""

    def __init__(self, client: AIClient | None = None):
        self.client = client or AIClient()

        # Initialize Redis cache with JSON serializer
        self.cache = Cache(
            Cache.REDIS,
            endpoint=os.environ.get("REDIS_HOST", "redis"),
            port=int(os.environ.get("REDIS_PORT", "6379")),
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
        suffix = file_path.suffix.lower()
        if suffix == ".pdf":
            text = await self._extract_text_from_pdf(file_path)
            result = self._extract_info_from_text(text, prompt)
        elif suffix in MIME_TYPES:
            result = self._extract_info_from_image(
                file_data, MIME_TYPES[suffix], prompt
            )
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
        logger.info("Extracting ticket information from text")
        json_obj = self.client.complete_json(
            [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant that extracts structured "
                        "information from text and returns it in JSON format. "
                        "You will receive text content followed by specific "
                        "extraction instructions. Always respond with valid "
                        "JSON only, no additional text or markdown formatting."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Here is the text to analyze:\n{text}\n\n"
                        f"Extraction instructions:\n{prompt}"
                    ),
                },
            ]
        )
        return self._validate_ticket_info(json_obj)

    def _extract_info_from_image(
        self, file_data: bytes, mime_type: str, prompt: str
    ) -> ExtractedTicketInfo:
        logger.info("Extracting ticket information from image")
        json_obj = self.client.complete_json(
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        image_content_from_bytes(file_data, mime_type),
                    ],
                }
            ]
        )
        return self._validate_ticket_info(json_obj)

    @staticmethod
    def _validate_ticket_info(json_obj: dict[str, Any]) -> ExtractedTicketInfo:
        logger.info(f"Information extracted: {json_obj}")
        if "items" not in json_obj:
            raise RuntimeError("No items found in the extracted JSON")
        return ExtractedTicketInfo.model_validate(json_obj)
