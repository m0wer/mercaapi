import os
import pytest
from app.nutrition import GeminiNutritionalFactsExtractor


@pytest.fixture
def extractor():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        pytest.skip("GEMINI_API_KEY environment variable not set")
    return GeminiNutritionalFactsExtractor(api_key)


# Define all test cases as a list of tuples (image_url, expected_output)
test_cases = [
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
    (
        "https://prod-mercadona.imgix.net/images/e9094a9837bad1b646cafa08476dcc32.jpg?fit=crop&h=1600&w=1600",
        {
            "calories_kJ": None,
            "calories_kcal": None,
            "total_fat": None,
            "saturated_fat": None,
            "polyunsaturated_fat": None,
            "monounsaturated_fat": None,
            "trans_fat": None,
            "total_carbohydrate": None,
            "dietary_fiber": None,
            "total_sugars": None,
            "protein": None,
            "salt": None,
        },
    ),
    (
        "https://prod-mercadona.imgix.net/images/9e525520b7c03aed08536ea31877293d.jpg?fit=crop&h=1600&w=1600",
        {
            "calories_kJ": 2100,
            "calories_kcal": 501,
            "total_fat": 25,
            "saturated_fat": 14,
            "polyunsaturated_fat": None,
            "monounsaturated_fat": None,
            "trans_fat": None,
            "total_carbohydrate": 64,
            "dietary_fiber": None,
            "total_sugars": 45,
            "protein": 5.1,
            "salt": 0.44,
        },
    ),
    (
        "https://prod-mercadona.imgix.net/images/364c378b9cb83ffc2450203f335152b4.jpg?fit=crop&h=1600&w=1600",
        {
            "calories_kJ": 2218,
            "calories_kcal": 531,
            "total_fat": 34.3,
            "saturated_fat": 12.3,
            "polyunsaturated_fat": None,
            "monounsaturated_fat": None,
            "trans_fat": None,
            "total_carbohydrate": 51.2,
            "dietary_fiber": 1.9,
            "total_sugars": None,
            "protein": 4.5,
            "salt": 0.56,
        },
    ),
]


def test_nutritional_facts_accuracy_gt_80(extractor):
    total_tests = len(test_cases)
    passed_tests = 0
    failed_tests = []

    for idx, (image_url, expected_output) in enumerate(test_cases, start=1):
        try:
            # Execute the method under test
            result = extractor.process_image_url(image_url)

            # Compare the result with the expected output
            assert (
                result == expected_output
            ), f"Test case {idx} failed.\nURL: {image_url}\nExpected: {expected_output}\nGot: {result}"
            passed_tests += 1
        except AssertionError as e:
            failed_tests.append(str(e))
            # Continue to next test case without halting

    success_rate = (passed_tests / total_tests) * 100
    print(f"\nTest Success Rate: {success_rate:.2f}% ({passed_tests}/{total_tests})")

    # Log all failed test cases
    if failed_tests:
        for failure in failed_tests:
            print(failure)

    # Assert that the success rate meets the requirement
    assert (
        success_rate >= 80
    ), f"Success rate {success_rate:.2f}% is below the required 80%."
