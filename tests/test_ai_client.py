import json

import pytest

from app.ai.client import (
    AIClient,
    AIClientError,
    image_content_from_bytes,
    image_content_from_url,
)


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text or json.dumps(self._payload)

    def json(self):
        return self._payload


def make_client() -> AIClient:
    return AIClient(api_key="test-key", base_url="https://ai.example.com/v1/")


def chat_payload(content: str) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


def test_base_url_trailing_slash_stripped():
    client = make_client()
    assert client.base_url == "https://ai.example.com/v1"


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("AI_API_KEY", raising=False)
    with pytest.raises(ValueError):
        AIClient()


def test_complete_returns_content(monkeypatch):
    client = make_client()
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return FakeResponse(200, chat_payload("hello"))

    monkeypatch.setattr("app.ai.client.requests.post", fake_post)
    result = client.complete([{"role": "user", "content": "hi"}])

    assert result == "hello"
    assert captured["url"] == "https://ai.example.com/v1/chat/completions"
    assert captured["json"]["model"] == client.model
    assert captured["headers"]["Authorization"] == "Bearer test-key"


def test_complete_json_strips_markdown_fences(monkeypatch):
    client = make_client()
    content = '```json\n{"calories_kcal": 100}\n```'
    monkeypatch.setattr(
        "app.ai.client.requests.post",
        lambda *a, **k: FakeResponse(200, chat_payload(content)),
    )
    assert client.complete_json([{"role": "user", "content": "x"}]) == {
        "calories_kcal": 100
    }


def test_complete_json_invalid_json_raises(monkeypatch):
    client = make_client()
    monkeypatch.setattr(
        "app.ai.client.requests.post",
        lambda *a, **k: FakeResponse(200, chat_payload("not json")),
    )
    with pytest.raises(AIClientError):
        client.complete_json([{"role": "user", "content": "x"}])


def test_non_retryable_error_raises(monkeypatch):
    client = make_client()
    monkeypatch.setattr(
        "app.ai.client.requests.post",
        lambda *a, **k: FakeResponse(400, {"error": "bad request"}),
    )
    with pytest.raises(AIClientError):
        client.complete([{"role": "user", "content": "x"}])


def test_retryable_error_retries_then_succeeds(monkeypatch):
    client = make_client()
    responses = [
        FakeResponse(429, {"error": "rate limited"}),
        FakeResponse(200, chat_payload("recovered")),
    ]
    monkeypatch.setattr(
        "app.ai.client.requests.post", lambda *a, **k: responses.pop(0)
    )
    # Speed up the retry wait for tests.
    monkeypatch.setattr(AIClient.complete.retry, "wait", lambda *a, **k: 0)
    assert client.complete([{"role": "user", "content": "x"}]) == "recovered"


def test_image_content_from_url():
    part = image_content_from_url("https://example.com/img.jpg")
    assert part == {
        "type": "image_url",
        "image_url": {"url": "https://example.com/img.jpg"},
    }


def test_image_content_from_bytes():
    part = image_content_from_bytes(b"abc", "image/png")
    assert part["type"] == "image_url"
    assert part["image_url"]["url"].startswith("data:image/png;base64,")
