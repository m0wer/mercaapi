"""OpenAI-compatible chat completions client.

Works with any OpenAI-compatible endpoint (OpenAI, proxies, local servers).
Configured through environment variables:

- ``AI_BASE_URL``: base URL of the API (default: ``https://api.openai.com/v1``)
- ``AI_API_KEY``: API key (required)
- ``AI_MODEL``: model used for both text and vision requests
  (default: ``gpt-5.4-mini``)
"""

import base64
import json
import os
import re
from datetime import datetime
from typing import Any

import requests
from loguru import logger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-5.4-mini"

JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*\n?|\n?\s*```\s*$")


class AIClientError(Exception):
    """Raised when the AI endpoint returns an error or unusable response."""


class RetryableAIError(AIClientError):
    """Raised for transient errors (rate limits, server errors, timeouts)."""


def image_content_from_url(url: str) -> dict[str, Any]:
    """Build an image content part from a remote image URL."""
    return {"type": "image_url", "image_url": {"url": url}}


def image_content_from_bytes(
    data: bytes, mime_type: str = "image/jpeg"
) -> dict[str, Any]:
    """Build an image content part from raw image bytes (base64 data URL)."""
    encoded = base64.b64encode(data).decode()
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
    }


class AIClient:
    """Minimal OpenAI-compatible chat completions client with JSON helpers."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int = 120,
    ):
        self.api_key = api_key or os.environ.get("AI_API_KEY")
        if not self.api_key:
            raise ValueError("AI_API_KEY environment variable is not set")
        self.base_url = (
            base_url or os.environ.get("AI_BASE_URL") or DEFAULT_BASE_URL
        ).rstrip("/")
        self.model = model or os.environ.get("AI_MODEL") or DEFAULT_MODEL
        self.timeout = timeout

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type(RetryableAIError),
        reraise=True,
    )
    def complete(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.1,
        max_tokens: int | None = None,
    ) -> str:
        """Run a chat completion and return the assistant message content."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        start = datetime.now()
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            raise RetryableAIError(f"Request to AI endpoint failed: {e}") from e
        elapsed = (datetime.now() - start).total_seconds()
        logger.debug(f"AI request to {self.model} took {elapsed:.3f} seconds")

        if response.status_code in (429, 500, 502, 503, 504):
            raise RetryableAIError(
                f"AI endpoint returned {response.status_code}: {response.text[:500]}"
            )
        if response.status_code != 200:
            raise AIClientError(
                f"AI endpoint returned {response.status_code}: {response.text[:500]}"
            )

        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise AIClientError(f"Unexpected AI response format: {data}") from e
        if content is None:
            raise AIClientError(f"AI response has no content: {data}")
        logger.debug(f"AI usage: {data.get('usage', {})}")
        return content

    def complete_json(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.1,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Run a chat completion and parse the response as a JSON object."""
        content = self.complete(
            messages, temperature=temperature, max_tokens=max_tokens
        )
        json_str = JSON_FENCE_RE.sub("", content).strip()
        try:
            result = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise AIClientError(
                f"Failed to parse AI response as JSON: {content[:500]}"
            ) from e
        if not isinstance(result, dict):
            raise AIClientError(f"Expected a JSON object, got: {type(result)}")
        return result
