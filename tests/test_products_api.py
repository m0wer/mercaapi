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
    response = client.get("/products/999")
    assert response.status_code == 404


def test_price_history_only_in_detail_endpoint(client, session, test_data):
    from datetime import datetime
    from app.models import PriceHistory
    from app.shared.cache import get_all_products
    from app.models import ProductPublic

    session.add(PriceHistory(product_id="1", price=1.0, timestamp=datetime(2026, 1, 1)))
    session.add(
        PriceHistory(
            product_id="1",
            price=1.1,
            timestamp=datetime(2026, 6, 1),
            warehouse_id=None,
        )
    )
    session.commit()

    # Detail endpoint loads price history from the database.
    detail = client.get("/products/1")
    assert detail.status_code == 200
    assert len(detail.json()["price_history"]) == 2

    # The listing (served from the in-memory cache) does not carry it.
    listing = client.get("/products/")
    assert listing.status_code == 200
    product = next(p for p in listing.json() if p["id"] == "1")
    assert product["price_history"] == []

    # Cached, detached products must validate without touching the session.
    cached = get_all_products(session)
    for item in cached:
        public = ProductPublic.model_validate(item)
        assert public.price_history == []


def test_get_categories(client, test_data):
    response = client.get("/categories/")
    assert response.status_code == 200
    assert len(response.json()) == 2
