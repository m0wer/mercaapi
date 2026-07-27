def test_get_products(client, test_data):
    response = client.get("/products/")
    assert response.status_code == 200
    products = response.json()
    assert len(products) == 3
    names = {product["name"] for product in products}
    assert names == {"Apple", "Banana", "Carrot"}


def test_get_products_pagination(client, test_data):
    response = client.get("/products/", params={"skip": 1, "limit": 1})
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_get_product_by_id(client, test_data):
    response = client.get("/products/1")
    assert response.status_code == 200
    product = response.json()
    assert product["name"] == "Apple"
    assert product["nutritional_information"]["calories"] == 52
    # Category ids 1-19 are food categories.
    assert product["is_food"] is True


def test_get_product_not_found(client, test_data):
    response = client.get("/products/nonexistent")
    assert response.status_code == 404


def test_get_categories(client, test_data):
    response = client.get("/categories/")
    assert response.status_code == 200
    assert len(response.json()) == 2
