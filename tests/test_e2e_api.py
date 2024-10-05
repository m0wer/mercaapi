import pytest
from fastapi.testclient import TestClient


def test_get_products(client: TestClient, test_data):
    response = client.get("/products")
    assert response.status_code == 200
    products = response.json()
    assert len(products) == 3
    assert any(product["name"] == "Apple" for product in products)


def test_get_product(client: TestClient, test_data):
    # Get the first product from the database
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


@pytest.mark.xfail
def test_closest_product_by_name(client: TestClient, test_data):
    response = client.get("/products/closest?name=apple")
    assert response.status_code == 200
    matches = response.json()
    assert len(matches) > 0
    assert matches[0]["product"]["name"] == "Apple"
    assert matches[0]["score"] == 70.0


@pytest.mark.xfail
def test_closest_product_by_price(client: TestClient, test_data):
    response = client.get("/products/closest?unit_price=0.6")
    assert response.status_code == 200
    matches = response.json()
    assert len(matches) > 0
    assert matches[0]["product"]["name"] == "Banana"


@pytest.mark.xfail
def test_closest_product_by_name_and_price(client: TestClient, test_data):
    response = client.get("/products/closest?name=carrot&unit_price=0.7")
    assert response.status_code == 200
    matches = response.json()
    assert len(matches) > 0
    assert matches[0]["product"]["name"] == "Carrot"


@pytest.mark.xfail
def test_closest_product_no_params(client: TestClient, test_data):
    response = client.get("/products/closest")
    assert response.status_code == 400
