import os
import pytest

from fastapi.testclient import TestClient


@pytest.mark.xfail
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
    expected_response = {
        "date": "09/12/2023",
        "items": [
            {
                "name": "ARANDANO 225 GR",
                "quantity": 1,
                "total_price": 3.15,
                "unit_price": 3.15,
            },
            {
                "name": "BACON LONCHAS",
                "quantity": 1,
                "total_price": 2.02,
                "unit_price": 2.02,
            },
            {
                "name": "BANANA",
                "quantity": 1,
                "total_price": 1.59,
                "unit_price": 1.45,
            },
            {"name": "BARREÑO", "quantity": 1, "total_price": 2.2, "unit_price": 2.2},
            {
                "name": "BOLSA PLASTICO",
                "quantity": 3,
                "total_price": 0.45,
                "unit_price": 0.15,
            },
            {
                "name": "FRAMBUESA 170 GR",
                "quantity": 1,
                "total_price": 2.5,
                "unit_price": 2.5,
            },
            {
                "name": "HIGIENICO DOBLE ROLL",
                "quantity": 2,
                "total_price": 8.8,
                "unit_price": 4.4,
            },
            {
                "name": "KEFIR FRESA-PLATANO",
                "quantity": 1,
                "total_price": 0.95,
                "unit_price": 0.95,
            },
            {
                "name": "KEFIR VEGETAL COCO",
                "quantity": 2,
                "total_price": 2.3,
                "unit_price": 1.15,
            },
            {"name": "KÉFIR", "quantity": 6, "total_price": 8.4, "unit_price": 1.4},
            {
                "name": "LOTE 3 BAYETAS MICRO",
                "quantity": 1,
                "total_price": 1.8,
                "unit_price": 1.8,
            },
            {"name": "PANCETA", "quantity": 1, "total_price": 2.25, "unit_price": 2.25},
            {
                "name": "QUESO FRESCO ENSALAD",
                "quantity": 1,
                "total_price": 1.95,
                "unit_price": 1.95,
            },
            {
                "name": "QUESO HAVARTI LIGHT",
                "quantity": 1,
                "total_price": 2.8,
                "unit_price": 2.8,
            },
            {
                "name": "RODILLO QUITAPELUSAS",
                "quantity": 1,
                "total_price": 1.75,
                "unit_price": 1.75,
            },
            {
                "name": "SALMOREJO FRESCO",
                "quantity": 3,
                "total_price": 3.75,
                "unit_price": 1.25,
            },
            {
                "name": "T.CHERRY 500 GR",
                "quantity": 1,
                "total_price": 1.95,
                "unit_price": 1.95,
            },
        ],
        "ticket_number": 3938016274335,
        "time": "14:51",
        "total_price": 48.61,
    }

    # Parse the JSON response
    ticket_data = response.json()

    ticket_data["items"].sort(key=lambda x: x["name"])

    # Assert the entire response matches the expected data
    assert (
        ticket_data == expected_response
    ), f"Response mismatch:\nExpected: {expected_response}\nActual: {ticket_data}"

    print("Ticket upload test passed successfully!")
