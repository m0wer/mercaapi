import pymupdf
from loguru import logger

from app.vision.prompts import ticket_info
from app.vision.gemini import GeminiImageInformationExtractor


class TicketImageInformationExtractor(GeminiImageInformationExtractor):
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash-latest"):
        super().__init__(api_key, model)
        self.prompt = ticket_info

    @staticmethod
    def convert_pdf_to_images(pdf_data):
        images = []
        with pymupdf.open(stream=pdf_data, filetype="pdf") as doc:
            for page in doc:
                pix = page.get_pixmap(dpi=200)
                img_data = pix.tobytes("jpeg")
                with open(f"page_{page.number}.jpeg", "wb") as f:
                    f.write(img_data)
                images.append((img_data, "image/jpeg"))
        return images

    def extract_ticket_info(self, file_data, mime_type) -> dict:
        logger.info("Processing ticket from bytes")
        if mime_type == "application/pdf":
            ticket_images = self.convert_pdf_to_images(file_data)
        else:
            ticket_images = [(file_data, mime_type)]
        files = self.upload_files(ticket_images)
        extract_info = self.extract_info_from_files(files, self.prompt)
        return extract_info
