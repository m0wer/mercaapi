from datetime import datetime
from typing import Union


from sqlmodel import SQLModel, Field, Relationship
from pydantic import BaseModel


class Category(SQLModel, table=True):
    id: int = Field(primary_key=True)
    name: str
    parent_id: int | None = Field(default=None, foreign_key="category.id")

    products: list["Product"] = Relationship(back_populates="category")


class Product(SQLModel, table=True):
    id: str = Field(primary_key=True)
    ean: str
    slug: str
    brand: str | None
    name: str
    price: float
    category_id: int = Field(foreign_key="category.id")
    description: str | None
    origin: str | None
    packaging: str | None
    unit_name: str | None
    unit_size: float | None
    is_variable_weight: bool = False
    is_pack: bool = False

    category: Category = Relationship(back_populates="products")
    images: list["ProductImage"] = Relationship(back_populates="product")
    price_history: list["PriceHistory"] = Relationship(back_populates="product")
    nutritional_information: Union["NutritionalInformation", None] = Relationship(
        back_populates="product"
    )


class ProductImage(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    product_id: str = Field(foreign_key="product.id")
    zoom_url: str
    regular_url: str
    thumbnail_url: str
    perspective: int

    product: Product = Relationship(back_populates="images")


class PriceHistory(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    product_id: str = Field(foreign_key="product.id")
    price: float
    timestamp: datetime

    product: Product = Relationship(back_populates="price_history")


class NutritionalInformation(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    product_id: str = Field(foreign_key="product.id")
    calories: float | None
    total_fat: float | None
    saturated_fat: float | None
    polyunsaturated_fat: float | None
    monounsaturated_fat: float | None
    trans_fat: float | None
    total_carbohydrate: float | None
    dietary_fiber: float | None
    total_sugars: float | None
    protein: float | None
    salt: float | None

    product: Product = Relationship(back_populates="nutritional_information")


class ProductMatch(BaseModel):
    score: float
    product: Product
