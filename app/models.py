from datetime import datetime
from typing import Union


from sqlmodel import SQLModel, Field, Relationship
from pydantic import BaseModel, model_validator


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


class TicketItem(BaseModel):
    name: str
    quantity: int = 1
    total_price: float | None = None
    unit_price: float | None = None

    @model_validator(mode="before")
    @classmethod
    def guess_unit_price(cls, data: dict):
        if "unit_price" not in data or data["unit_price"] is None:
            if (
                "total_price" in data
                and data["total_price"] is not None
                and data["total_price"] != 0
                and data["quantity"] != 0
            ):
                data["unit_price"] = data["total_price"] / data["quantity"]
        return data


class TicketInfo(BaseModel):
    ticket_number: int | None = None
    date: str | None = None
    time: str | None = None
    total_price: float | None = None
    items: list[TicketItem]


class ProductInfo(BaseModel):
    product: Product
    is_food: bool
    total_weight: float | None = None
    total_calories: float | None = None
    total_protein: float | None = None
    total_carbs: float | None = None
    total_fat: float | None = None


class TicketStats(BaseModel):
    total_calories: float
    total_proteins: float
    total_carbs: float
    total_fat: float
    total_fiber: float
    avg_cost_per_daily_kcal: float
    avg_cost_per_100g_protein: float
    avg_cost_per_100g_carb: float
    avg_cost_per_100g_fat: float
    kcal_per_euro: float
    number_of_daily_doses: float
    average_daily_cost: float
    protein_ratio: float
    carb_ratio: float
    fat_ratio: float
    food_percentage: float
    total_food_amount: float
    food_products: list[ProductInfo]
    non_food_products: list[ProductInfo]
