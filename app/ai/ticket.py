from loguru import logger
from typing import Dict, Any

from app.ai.prompts import ticket_info
from app.ai.gemini import GeminiFileInformationExtractor


class TicketImageInformationExtractor(GeminiFileInformationExtractor):
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash-latest"):
        super().__init__(api_key, model)
        self.prompt = ticket_info

    def extract_ticket_info(self, file_data: bytes, mime_type: str) -> Dict[str, Any]:
        logger.info("Processing ticket from bytes")
        try:
            file_uri = self.upload_file(file_data, mime_type)
            extract_info = self.extract_info_from_file(file_uri, mime_type, self.prompt)
            return extract_info
        except Exception as e:
            logger.error(f"Error in extract_ticket_info: {str(e)}")
            raise
