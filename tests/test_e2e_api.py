import pytest

from fastapi.testclient import TestClient


def test_get_products(client: TestClient, test_data):
    response = client.get("/products")
    assert response.status_code == 200
    products = response.json()
    assert len(products) == 3
    assert any(product["name"] == "Apple" for product in products)
    assert all("nutritional_information" in product for product in products)
    assert all("images" in product for product in products)


def test_get_product(client: TestClient, test_data):
    response = client.get("/products")
    products = response.json()
    first_product_id = products[0]["id"]

    response = client.get(f"/products/{first_product_id}")
    assert response.status_code == 200
    product = response.json()
    assert product["name"] in ["Apple", "Banana", "Carrot"]
    assert "price" in product
    assert "images" in product
    assert "nutritional_information" in product


def test_get_product_not_found(client: TestClient, test_data):
    response = client.get("/products/999")
    assert response.status_code == 404


def test_get_categories(client: TestClient, test_data):
    response = client.get("/categories")
    assert response.status_code == 200
    categories = response.json()
    assert len(categories) == 2
    assert any(category["name"] == "Fruits" for category in categories)


def test_closest_product_by_name(client: TestClient, test_data):
    response = client.get("/products/closest?name=apple")
    assert response.status_code == 200
    matches = response.json()
    assert len(matches) > 0
    assert matches[0]["product"]["name"] == "Apple"
    assert matches[0]["score"] == 70.0


def test_closest_product_by_price(client: TestClient, test_data):
    response = client.get("/products/closest?unit_price=0.6&threshold=10")
    assert response.status_code == 200
    matches = response.json()
    assert len(matches) > 0
    assert matches[0]["product"]["name"] == "Banana"


def test_closest_product_by_name_and_price(client: TestClient, test_data):
    response = client.get("/products/closest?name=carrot&unit_price=0.7")
    assert response.status_code == 200
    matches = response.json()
    assert len(matches) > 0
    assert matches[0]["product"]["name"] == "Carrot"


def test_closest_product_no_params(client: TestClient, test_data):
    response = client.get("/products/closest")
    assert response.status_code == 400


@pytest.mark.xfail
def test_process_ticket_and_calculate_stats(client: TestClient, test_data):
    # Mock ticket data
    ticket_data = {"file": ("ticket.jpg", b"mock image data", "image/jpeg")}

    response = client.post("/ticket/", files=ticket_data)
    assert response.status_code == 200
    ticket_stats = response.json()

    assert "items" in ticket_stats
    assert len(ticket_stats["items"]) > 0

    for item in ticket_stats["items"]:
        assert "product" in item
        assert "original_name" in item
        assert "quantity" in item
        assert "unit_price" in item
        assert "total_price" in item
        assert "stats" in item

        product = item["product"]
        assert "id" in product
        assert "name" in product
        assert "price" in product
        assert "nutritional_information" in product
        assert "images" in product

        if item["stats"]:
            stats = item["stats"]
            assert "calories" in stats
            assert "proteins" in stats
            assert "carbs" in stats
            assert "fat" in stats
            assert "fiber" in stats
            assert "cost_per_daily_kcal" in stats
            assert "cost_per_100g_protein" in stats
            assert "cost_per_100g_carb" in stats
            assert "cost_per_100g_fat" in stats
            assert "kcal_per_euro" in stats
