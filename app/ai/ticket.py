from loguru import logger

from app.ai.prompts import ticket_info
from app.ai.gemini import GeminiFileInformationExtractor
from app.models import TicketInfo


class TicketImageInformationExtractor(GeminiFileInformationExtractor):
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash-latest"):
        super().__init__(api_key, model)
        self.prompt = ticket_info

    async def extract_ticket_info(self, file_data: bytes, mime_type: str) -> TicketInfo:
        logger.info("Processing ticket from bytes")
        try:
            extract_info = await self.extract_ticket_info(file_data, mime_type)
            return TicketInfo.parse_obj(extract_info)
        except Exception as e:
            logger.error(f"Error in extract_ticket_info: {str(e)}")
            raise
