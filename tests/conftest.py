import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from main import api_router
from app.database import get_session
from app.models import Product, Category, ProductImage, NutritionalInformation


@pytest.fixture(name="engine")
def engine_fixture():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="session")
def session_fixture(engine):
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(name="client")
def client_fixture(engine, session):
    def get_session_override():
        return session

    api_router.dependency_overrides[get_session] = get_session_override

    client = TestClient(api_router)
    yield client
    api_router.dependency_overrides.clear()


@pytest.fixture(name="test_data")
def test_data_fixture(session):
    # Create test categories
    category1 = Category(name="Fruits")
    category2 = Category(name="Vegetables")
    session.add(category1)
    session.add(category2)
    session.flush()

    # Create test products
    products = [
        Product(
            id=1,
            ean="1234567890123",
            slug="apple",
            name="Apple",
            price=1.0,
            category_id=category1.id,
        ),
        Product(
            id=2,
            ean="2345678901234",
            slug="banana",
            name="Banana",
            price=0.5,
            category_id=category1.id,
        ),
        Product(
            id=3,
            ean="3456789012345",
            slug="carrot",
            name="Carrot",
            price=0.75,
            category_id=category2.id,
        ),
    ]
    session.add_all(products)
    session.flush()

    # Create test product images
    images = [
        ProductImage(
            product_id=products[0].id,
            zoom_url="http://example.com/apple.jpg",
            regular_url="http://example.com/apple_regular.jpg",
            thumbnail_url="http://example.com/apple_thumb.jpg",
            perspective=1,
        ),
        ProductImage(
            product_id=products[1].id,
            zoom_url="http://example.com/banana.jpg",
            regular_url="http://example.com/banana_regular.jpg",
            thumbnail_url="http://example.com/banana_thumb.jpg",
            perspective=1,
        ),
    ]
    session.add_all(images)

    # Create test nutritional information
    nutritional_info = [
        NutritionalInformation(
            product_id=products[0].id,
            calories=52,
            total_fat=0.2,
            total_carbohydrate=14,
            protein=0.3,
        ),
        NutritionalInformation(
            product_id=products[1].id,
            calories=89,
            total_fat=0.3,
            total_carbohydrate=23,
            protein=1.1,
        ),
    ]
    session.add_all(nutritional_info)

    session.commit()

    yield session
