from sqlmodel import Session, select

from app.models import (
    AvailabilityHistory,
    Category,
    PriceHistory,
    Product,
    ProductWarehouseStatus,
    Warehouse,
)
from app.warehouses import sync_warehouse_availability


def seed(engine):
    with Session(engine) as session:
        session.add(Category(id=1, name="Aceite, especias y salsas"))
        session.add(Warehouse(id="mad3", postal_code="28001"))
        session.add_all(
            [
                Product(
                    id="100",
                    ean="1",
                    slug="aceite",
                    name="Aceite",
                    price=5.0,
                    category_id=1,
                ),
                Product(
                    id="200",
                    ean="2",
                    slug="vinagre",
                    name="Vinagre",
                    price=1.2,
                    category_id=1,
                ),
            ]
        )
        session.commit()


def test_first_sync_creates_statuses_and_history(engine):
    seed(engine)
    catalog = {
        "100": {"price": 5.0, "category_id": 1},
        "200": {"price": 1.5, "category_id": 1},
    }
    stats = sync_warehouse_availability(engine, "mad3", catalog)

    assert stats == {"appeared": 2, "disappeared": 0, "price_changes": 1}
    with Session(engine) as session:
        statuses = session.exec(select(ProductWarehouseStatus)).all()
        assert len(statuses) == 2
        assert all(status.available for status in statuses)
        history = session.exec(select(AvailabilityHistory)).all()
        assert len(history) == 2
        # Price recorded only where it diverges from the main product price.
        prices = session.exec(select(PriceHistory)).all()
        assert len(prices) == 1
        assert prices[0].product_id == "200"
        assert prices[0].warehouse_id == "mad3"
        assert prices[0].price == 1.5


def test_product_disappears_and_reappears(engine):
    seed(engine)
    full = {
        "100": {"price": 5.0, "category_id": 1},
        "200": {"price": 1.2, "category_id": 1},
    }
    partial = {"100": {"price": 5.0, "category_id": 1}}

    sync_warehouse_availability(engine, "mad3", full)
    stats = sync_warehouse_availability(engine, "mad3", partial)
    assert stats == {"appeared": 0, "disappeared": 1, "price_changes": 0}

    with Session(engine) as session:
        status = session.get(ProductWarehouseStatus, ("200", "mad3"))
        assert status is not None
        assert status.available is False

    stats = sync_warehouse_availability(engine, "mad3", full)
    assert stats == {"appeared": 1, "disappeared": 0, "price_changes": 0}

    with Session(engine) as session:
        status = session.get(ProductWarehouseStatus, ("200", "mad3"))
        assert status is not None and status.available is True
        history = session.exec(
            select(AvailabilityHistory)
            .where(AvailabilityHistory.product_id == "200")
            .order_by(AvailabilityHistory.id)  # type: ignore[arg-type]
        ).all()
        assert [row.available for row in history] == [True, False, True]


def test_repeated_sync_is_idempotent(engine):
    seed(engine)
    catalog = {"100": {"price": 5.0, "category_id": 1}}
    sync_warehouse_availability(engine, "mad3", catalog)
    stats = sync_warehouse_availability(engine, "mad3", catalog)

    assert stats == {"appeared": 0, "disappeared": 0, "price_changes": 0}
    with Session(engine) as session:
        history = session.exec(select(AvailabilityHistory)).all()
        assert len(history) == 1


def test_price_change_recorded_per_warehouse(engine):
    seed(engine)
    sync_warehouse_availability(engine, "mad3", {"100": {"price": 5.0, "category_id": 1}})
    stats = sync_warehouse_availability(
        engine, "mad3", {"100": {"price": 5.5, "category_id": 1}}
    )

    assert stats["price_changes"] == 1
    with Session(engine) as session:
        status = session.get(ProductWarehouseStatus, ("100", "mad3"))
        assert status is not None and status.price == 5.5
        prices = session.exec(select(PriceHistory)).all()
        assert len(prices) == 1
        assert prices[0].price == 5.5
        assert prices[0].warehouse_id == "mad3"


def test_unknown_product_in_catalog_is_ignored(engine):
    seed(engine)
    catalog = {"999": {"price": 2.0, "category_id": 1}}
    stats = sync_warehouse_availability(engine, "mad3", catalog)

    assert stats == {"appeared": 0, "disappeared": 0, "price_changes": 0}
    with Session(engine) as session:
        assert session.exec(select(ProductWarehouseStatus)).all() == []


def test_warehouses_endpoint(client, session):
    session.add(Warehouse(id="mad3", postal_code="28001"))
    session.add(Warehouse(id="bcn1", postal_code="08001", active=False))
    session.commit()

    response = client.get("/warehouses/")
    assert response.status_code == 200
    warehouses = {wh["id"]: wh for wh in response.json()}
    assert warehouses["mad3"]["active"] is True
    assert warehouses["bcn1"]["active"] is False


def test_product_availability_endpoint(client, session, test_data):
    session.add(Warehouse(id="mad3", postal_code="28001"))
    session.add(
        ProductWarehouseStatus(
            product_id="1", warehouse_id="mad3", available=True, price=1.0
        )
    )
    session.add(
        AvailabilityHistory(product_id="1", warehouse_id="mad3", available=True)
    )
    session.commit()

    response = client.get("/products/1/availability")
    assert response.status_code == 200
    availability = response.json()
    assert len(availability) == 1
    assert availability[0]["warehouse_id"] == "mad3"
    assert availability[0]["available"] is True

    response = client.get("/products/1/availability/history")
    assert response.status_code == 200
    assert len(response.json()) == 1

    response = client.get("/products/999/availability")
    assert response.status_code == 404
