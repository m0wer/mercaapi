from loguru import logger

from app.vision.prompts import ticket_info
from app.vision.gemini import GeminiImageInformationExtractor


class TicketImageInformationExtractor(GeminiImageInformationExtractor):
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash-latest"):
        super().__init__(api_key, model)
        self.prompt = ticket_info

    def extract_ticket_info(self, file_data, mime_type) -> dict:
        logger.info("Processing ticket from bytes")
        file_uri = self.upload_file(file_data, mime_type)
        extract_info = self.extract_info_from_file(file_uri, self.prompt)
        return extract_info
