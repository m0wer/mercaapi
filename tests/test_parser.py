import asyncio

import pytest
from sqlmodel import Session, select

import app.parser as parser
from app.models import Category, PriceHistory, Product, ProductImage


@pytest.fixture(name="seeded_engine")
def seeded_engine_fixture(engine):
    with Session(engine) as session:
        session.add(Category(id=1, name="Aceite, especias y salsas"))
        session.add(
            Product(
                id="1000",
                ean="1234567890123",
                slug="aceite",
                brand="Hacendado",
                name="Aceite de oliva",
                price=5.0,
                category_id=1,
            )
        )
        # An image triggers the joined eager load that used to break updates.
        session.add(
            ProductImage(
                product_id="1000",
                zoom_url="http://example.com/zoom.jpg",
                regular_url="http://example.com/regular.jpg",
                thumbnail_url="http://example.com/thumb.jpg",
                perspective=1,
            )
        )
        session.commit()
    return engine


def test_update_existing_product_price(seeded_engine, monkeypatch):
    """Regression test: updating an existing product must not fail because of
    joined eager loads, and price changes must be recorded in history."""

    async def fake_parse_products(session, category_id, rate_limiter, existing_ids):
        yield Product(
            id="1000",
            ean="1234567890123",
            slug="aceite",
            brand="Hacendado",
            name="Aceite de oliva virgen",
            price=6.5,
            category_id=1,
        )

    monkeypatch.setattr(parser, "parse_products", fake_parse_products)

    new_count, updated_count = asyncio.run(
        parser.parse_category_products(seeded_engine, None, 1, None)
    )

    assert new_count == 0
    assert updated_count == 1
    with Session(seeded_engine) as session:
        product = session.exec(
            select(Product).where(Product.id == "1000")
        ).unique().one()
        assert product.price == 6.5
        assert product.name == "Aceite de oliva virgen"
        history = session.exec(select(PriceHistory)).all()
        assert len(history) == 1
        assert history[0].price == 6.5


def test_add_new_product(seeded_engine, monkeypatch):
    async def fake_parse_products(session, category_id, rate_limiter, existing_ids):
        yield Product(
            id="2000",
            ean="9999999999999",
            slug="vinagre",
            brand="Hacendado",
            name="Vinagre de vino",
            price=1.2,
            category_id=1,
        )

    monkeypatch.setattr(parser, "parse_products", fake_parse_products)

    new_count, updated_count = asyncio.run(
        parser.parse_category_products(seeded_engine, None, 1, None)
    )

    assert new_count == 1
    assert updated_count == 0
    with Session(seeded_engine) as session:
        product = session.exec(
            select(Product).where(Product.id == "2000")
        ).unique().one()
        assert product.price == 1.2
        history = session.exec(select(PriceHistory)).all()
        assert len(history) == 1
