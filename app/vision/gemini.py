import json
import requests
from loguru import logger
import re
from typing import Dict, Any


class GeminiImageInformationExtractor:
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash-latest"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com"
        self.upload_url = f"{self.base_url}/upload/v1beta/files"
        self.generate_url = f"{self.base_url}/v1beta/models/{model}:generateContent"

    def upload_file(self, file_data: bytes, mime_type: str) -> str:
        # Get image metadata
        num_bytes = len(file_data)
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
        logger.debug(f"Initiating file upload with metadata: {data}")
        response = requests.post(
            f"{self.upload_url}?key={self.api_key}", headers=headers, data=data
        )
        if response.status_code != 200:
            raise Exception(
                f"Failed to initiate upload. Status code: {response.status_code}"
            )
        upload_url = response.headers["X-Goog-Upload-URL"]
        logger.debug(f"Upload URL: {upload_url}")

        # Upload the actual bytes
        headers = {
            "Content-Length": str(num_bytes),
            "X-Goog-Upload-Offset": "0",
            "X-Goog-Upload-Command": "upload, finalize",
        }
        logger.debug("Uploading file data")
        response = requests.post(upload_url, headers=headers, data=file_data)
        if response.status_code != 200:
            raise Exception(
                f"Failed to upload file. Status code: {response.status_code}"
            )
        file_info = response.json()
        logger.debug(f"Upload successful. File info: {file_info}")
        return file_info["file"]["uri"]

    def extract_info_from_file(self, file_uri: str, prompt: str) -> Dict[str, Any]:
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
            # Extract the JSON object from the response text
            logger.debug(f"Response text: {json_str}")
            json_str = re.sub(r"^```json\s*\n", "", json_str)
            json_str = re.sub(r"\n\s*```$", "", json_str)
            json_obj = json.loads(json_str)
            logger.info(f"Information extracted: {json_obj}")
            return json_obj
        else:
            logger.error(f"Error: {response.status_code}, {response.text}")
            raise Exception(f"Error: {response.status_code}, {response.text}")
