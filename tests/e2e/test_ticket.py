import os
from typing import Any

from fastapi.testclient import TestClient


def test_upload_ticket(client: TestClient):
    # Path to the test image file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    test_image_path = os.path.join(current_dir, "test_data/", "ticket.png")

    # Ensure the test image file exists
    assert os.path.exists(test_image_path), f"Test image not found at {test_image_path}"

    # Open the image file
    with open(test_image_path, "rb") as image_file:
        # Prepare the files for the multipart/form-data request
        files = {"file": ("ticket.png", image_file, "image/png")}

        # Send POST request to the endpoint
        response = client.post("/ticket/", files=files)

    # Check the response status code
    assert (
        response.status_code == 200
    ), f"Expected status code 200, but got {response.status_code}"

    # Define the expected complete response
    expected_response: dict[str, Any] = {
        "items": [],
    }

    # Parse the JSON response
    ticket_data = response.json()

    ticket_data["items"].sort(key=lambda x: x["name"])

    # Assert the entire response matches the expected data
    assert (
        ticket_data == expected_response
    ), f"Response mismatch:\nExpected: {expected_response}\nActual: {ticket_data}"

    print("Ticket upload test passed successfully!")
