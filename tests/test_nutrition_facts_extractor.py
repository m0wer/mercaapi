import json
import pytest
from unittest.mock import patch, Mock
from app.ai.nutrition_facts import NutritionFactsExtractor


@pytest.fixture
def extractor():
    api_key = "test_api_key"
    return NutritionFactsExtractor(api_key)


@pytest.mark.parametrize(
    "image_url,expected_output",
    [
        (
            "https://prod-mercadona.imgix.net/images/35fb9cb075a4ddd11ddf9eaf7a20dcc2.jpg?fit=crop&h=1600&w=1600",
            {
                "calories_kJ": 941,
                "calories_kcal": 226,
                "total_fat": 14.0,
                "saturated_fat": 1.3,
                "polyunsaturated_fat": None,
                "monounsaturated_fat": None,
                "trans_fat": None,
                "total_carbohydrate": 18.0,
                "dietary_fiber": 3.3,
                "total_sugars": 8.6,
                "protein": 5.3,
                "salt": 0.91,
            },
        ),
        (
            "https://prod-mercadona.imgix.net/images/602715e9a771a9d98e6b26dae428572e.jpg?fit=crop&h=1600&w=1600",
            {
                "calories_kJ": 91,
                "calories_kcal": 21,
                "total_fat": 0.0,
                "saturated_fat": 0.0,
                "polyunsaturated_fat": None,
                "monounsaturated_fat": None,
                "trans_fat": None,
                "total_carbohydrate": 4.8,
                "dietary_fiber": 0.5,
                "total_sugars": 4.8,
                "protein": 0.3,
                "salt": 0.03,
            },
        ),
        (
            "https://prod-mercadona.imgix.net/images/095dffa8053fb32c2c81a774a1aa1516.jpg?fit=crop&h=1600&w=1600",
            {
                "calories_kJ": 1926,
                "calories_kcal": 458,
                "total_fat": 16,
                "saturated_fat": 1.9,
                "polyunsaturated_fat": 2,
                "monounsaturated_fat": 12,
                "trans_fat": None,
                "total_carbohydrate": 71,
                "dietary_fiber": 3.5,
                "total_sugars": 20,
                "protein": 6.9,
                "salt": 0.54,
            },
        ),
    ],
)
@patch("app.ai.gemini.requests.post")
@patch("app.ai.gemini.requests.get")
def test_process_image_url(mock_get, mock_post, extractor, image_url, expected_output):
    # Mock the GET request to download the image
    mock_get.return_value = Mock(
        status_code=200, content=b"image_data", headers={"Content-Type": "image/jpeg"}
    )

    # Mock responses for the POST requests
    # 1. Initiate upload
    initiate_upload_response = Mock(
        status_code=200, headers={"X-Goog-Upload-URL": "https://upload.test"}
    )

    # 2. Upload image data
    upload_image_response = Mock(
        status_code=200, json=lambda: {"file": {"uri": "file_uri"}}
    )

    # 3. Generate content with extracted nutritional information
    generate_content_response = Mock(
        status_code=200,
        json=lambda: {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": f"```json\n{json.dumps(expected_output)}\n```"}
                        ]
                    }
                }
            ]
        },
    )

    # Set the side_effect for POST requests
    mock_post.side_effect = [
        initiate_upload_response,
        upload_image_response,
        generate_content_response,
    ]

    # Execute the method under test
    result = extractor.extract_nutrition_facts(image_url)

    # Assert the result matches the expected output
    assert result == expected_output
