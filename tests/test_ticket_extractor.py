import pytest

from app.ai.ticket import AIInformationExtractor
from app.models import ExtractedTicketInfo


class FakeAIClient:
    def __init__(self, response: dict):
        self.response = response
        self.calls: list = []

    def complete_json(self, messages, **kwargs):
        self.calls.append(messages)
        return self.response


TICKET_RESPONSE = {
    "ticket_number": 1234,
    "date": "01/05/2026",
    "time": "18:30",
    "total_price": 7.5,
    "items": [
        {"name": "LECHE ENTERA", "quantity": 2, "total_price": 3.0},
        {"name": "PAN", "quantity": 1, "unit_price": 4.5},
    ],
}


def make_extractor(response: dict) -> AIInformationExtractor:
    return AIInformationExtractor(client=FakeAIClient(response))  # type: ignore[arg-type]


def test_extract_info_from_text():
    extractor = make_extractor(TICKET_RESPONSE)
    info = extractor._extract_info_from_text("some ticket text", "prompt")

    assert isinstance(info, ExtractedTicketInfo)
    assert info.ticket_number == 1234
    assert len(info.items) == 2
    # unit price derived from total price
    assert info.items[0].unit_price == 1.5
    # total price derived from unit price
    assert info.items[1].total_price == 4.5


def test_extract_info_from_image():
    extractor = make_extractor(TICKET_RESPONSE)
    info = extractor._extract_info_from_image(b"fakeimage", "image/jpeg", "prompt")

    assert isinstance(info, ExtractedTicketInfo)
    assert info.total_price == 7.5
    # The image must be sent as a base64 data URL content part.
    messages = extractor.client.calls[0]  # type: ignore[attr-defined]
    image_parts = [
        part
        for part in messages[0]["content"]
        if isinstance(part, dict) and part.get("type") == "image_url"
    ]
    assert len(image_parts) == 1
    assert image_parts[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_missing_items_raises():
    extractor = make_extractor({"total_price": 3.0})
    with pytest.raises(RuntimeError):
        extractor._extract_info_from_text("text", "prompt")
