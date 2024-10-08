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

    # Parse the JSON response
    ticket_data = response.json()

    # Assert the exact values as per the expected output
    assert ticket_data["ticket_number"] == 388348
    assert ticket_data["date"] == "09/12/2023"
    assert ticket_data["time"] == "14:51"
    assert ticket_data["total_price"] == 48.61

    # Assert the items
    expected_items = [
        {
            "name": "QUESO HAVARTI LIGHT",
            "quantity": 1,
            "total_price": 2.80,
            "unit_price": 2.80,
        },
        {
            "name": "BOLSA PLASTICO",
            "quantity": 3,
            "total_price": 0.45,
            "unit_price": 0.15,
        },
        {"name": "KÉFIR", "quantity": 6, "total_price": 8.40, "unit_price": 1.40},
        {
            "name": "RODILLO QUITAPELUSAS",
            "quantity": 1,
            "total_price": 1.75,
            "unit_price": 1.75,
        },
        {
            "name": "KÉFIR FRESA-PLÁTANO",
            "quantity": 1,
            "total_price": 0.95,
            "unit_price": 0.95,
        },
        {
            "name": "KÉFIR VEGETAL COCO",
            "quantity": 2,
            "total_price": 2.30,
            "unit_price": 1.15,
        },
        {
            "name": "LOTE 3 BAYETAS MICRO",
            "quantity": 1,
            "total_price": 1.80,
            "unit_price": 1.80,
        },
        {"name": "BARREÑO", "quantity": 1, "total_price": 2.20, "unit_price": 2.20},
        {
            "name": "HIGIENICO DOBLE ROLL",
            "quantity": 2,
            "total_price": 8.80,
            "unit_price": 4.40,
        },
        {
            "name": "SALMOREJO FRESCO",
            "quantity": 3,
            "total_price": 3.75,
            "unit_price": 1.25,
        },
        {
            "name": "QUESO FRESCO ENSALAD",
            "quantity": 1,
            "total_price": 1.95,
            "unit_price": 1.95,
        },
        {
            "name": "ARÁNDANO 225 GR",
            "quantity": 1,
            "total_price": 3.15,
            "unit_price": 3.15,
        },
        {
            "name": "FRAMBUESA 170 GR",
            "quantity": 1,
            "total_price": 2.50,
            "unit_price": 2.50,
        },
        {
            "name": "T.CHERRY 500 GR",
            "quantity": 1,
            "total_price": 1.95,
            "unit_price": 1.95,
        },
        {"name": "PANCETA", "quantity": 1, "total_price": 2.25, "unit_price": 2.25},
        {
            "name": "BACON LONCHAS",
            "quantity": 1,
            "total_price": 2.02,
            "unit_price": 2.02,
        },
        {"name": "BANANA", "quantity": 1.094, "total_price": 1.59, "unit_price": 1.45},
    ]

    assert len(ticket_data["items"]) == len(expected_items)

    for actual_item, expected_item in zip(ticket_data["items"], expected_items):
        assert (
            actual_item == expected_item
        ), f"Mismatch in item: {actual_item} != {expected_item}"

    print("Ticket upload test passed successfully!")
