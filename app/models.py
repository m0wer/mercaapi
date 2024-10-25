from datetime import datetime
from typing import Union, Any, List, Tuple
from typing_extensions import Self

from sqlmodel import SQLModel, Field, Relationship
from pydantic import BaseModel, model_validator


# Base models
class CategoryBase(SQLModel):
    name: str
    parent_id: int | None = Field(default=None, foreign_key="category.id")


class ProductImageBase(SQLModel):
    zoom_url: str
    regular_url: str
    thumbnail_url: str
    perspective: int


class NutritionalInformationBase(SQLModel):
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


class ProductBase(SQLModel):
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


class PriceHistoryBase(SQLModel):
    price: float
    timestamp: datetime


class TicketBase(SQLModel):
    ticket_number: int | None = None
    date: str | None = None
    time: str | None = None
    total_price: float | None = None
    processed_at: datetime = Field(default_factory=datetime.utcnow)


class TicketItemBase(SQLModel):
    name: str
    quantity: int
    total_price: float
    unit_price: float


# DB models
class Category(CategoryBase, table=True):
    id: int = Field(primary_key=True)
    products: list["Product"] = Relationship(back_populates="category")


class ProductImage(ProductImageBase, table=True):
    id: int = Field(default=None, primary_key=True)
    product_id: str = Field(foreign_key="product.id")
    product: "Product" = Relationship(back_populates="images")


class NutritionalInformation(NutritionalInformationBase, table=True):
    id: int = Field(default=None, primary_key=True)
    product_id: str = Field(foreign_key="product.id")
    product: "Product" = Relationship(back_populates="nutritional_information")


class WrongMatchReport(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    original_name: str
    original_price: float
    wrong_match_id: str = Field(foreign_key="product.id")
    wrong_match: "Product" = Relationship(back_populates="wrong_match_reports")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="pending")  # pending, reviewed, rejected
    notes: str | None = None


class WrongNutritionReport(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    product_id: str = Field(foreign_key="product.id")
    product: "Product" = Relationship(back_populates="nutrition_reports")
    nutrition_id: int = Field(foreign_key="nutritionalinformation.id")
    nutritional_information: NutritionalInformation = Relationship()
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="pending")  # pending, reviewed, rejected
    notes: str | None = None


class Product(ProductBase, table=True):
    category: Category = Relationship(back_populates="products")
    images: List[ProductImage] = Relationship(
        back_populates="product", sa_relationship_kwargs={"lazy": "joined"}
    )
    price_history: List["PriceHistory"] = Relationship(back_populates="product")
    nutritional_information: Union[NutritionalInformation, None] = Relationship(
        back_populates="product", sa_relationship_kwargs={"lazy": "joined"}
    )
    wrong_match_reports: List[WrongMatchReport] = Relationship(
        back_populates="wrong_match"
    )
    nutrition_reports: List[WrongNutritionReport] = Relationship(
        back_populates="product"
    )


class PriceHistory(PriceHistoryBase, table=True):
    id: int = Field(default=None, primary_key=True)
    product_id: str = Field(foreign_key="product.id")
    product: Product = Relationship(back_populates="price_history")


class Ticket(TicketBase, table=True):
    id: int = Field(default=None, primary_key=True)
    items: List["TicketItem"] = Relationship(back_populates="ticket")


class TicketItem(TicketItemBase, table=True):
    id: int = Field(default=None, primary_key=True)
    ticket_id: int = Field(foreign_key="ticket.id")
    ticket: Ticket = Relationship(back_populates="items")
    matched_product_id: str | None = Field(default=None, foreign_key="product.id")
    matched_product: Product | None = Relationship()


# Helper functions
def is_food_category(category: Category) -> bool:
    if 1 <= category.id <= 19:
        return True
    if category.parent_id is not None:
        return 1 <= category.parent_id <= 19
    return False


# Public models
class CategoryPublic(CategoryBase):
    id: int


class ProductImagePublic(ProductImageBase):
    id: int
    product_id: str


class NutritionalInformationPublic(NutritionalInformationBase):
    id: int
    product_id: str


class ProductPublic(ProductBase):
    category: CategoryPublic
    images: List[ProductImagePublic] = []
    nutritional_information: NutritionalInformationPublic | None = None
    price_history: List["PriceHistoryPublic"] = []
    is_food: bool = False

    @model_validator(mode="after")
    def set_is_food(self) -> Self:
        self.is_food = is_food_category(Category.model_validate(self.category))
        return self


class PriceHistoryPublic(PriceHistoryBase):
    id: int
    product_id: str


# Stats and analysis models
class ItemStats(BaseModel):
    calories: float | None
    proteins: float | None
    carbs: float | None
    fat: float | None
    fiber: float | None
    cost_per_daily_kcal: float | None
    cost_per_100g_protein: float | None
    cost_per_100g_carb: float | None
    cost_per_100g_fat: float | None
    kcal_per_euro: float | None


class TicketItemPublic(BaseModel):
    product: ProductPublic
    original_name: str
    quantity: int
    unit_price: float
    total_price: float
    stats: ItemStats | None


class TicketStats(BaseModel):
    items: List[TicketItemPublic]


class ProductMatch(BaseModel):
    score: float
    product: ProductPublic


def default_quantity(v: Any) -> int:
    if v is None:
        return 1
    return v


class ExtractedTicketItem(BaseModel):
    name: str
    quantity: float = 1
    total_price: float | None = None
    unit_price: float | None = None

    @model_validator(mode="before")
    @classmethod
    def transform_quantity(cls, values: Any) -> Any:
        if isinstance(values, dict) and values.get("quantity") is None:
            values["quantity"] = 1.0
        return values

    @model_validator(mode="before")
    def calculate_prices(cls, values: Any) -> Any:
        # Handle cases where total_price is None
        if values.get("total_price") is None and values.get("unit_price") is not None:
            values["total_price"] = values["unit_price"] * values.get("quantity", 1)

        # Handle cases where unit_price is None
        if values.get("unit_price") is None and values.get("total_price") is not None:
            quantity = values.get("quantity", 1.0)
            if quantity > 0:
                values["unit_price"] = values["total_price"] / quantity
            else:
                values["unit_price"] = 0.0

        # If both prices are None, set them to 0
        if values.get("total_price") is None and values.get("unit_price") is None:
            values["total_price"] = 0.0
            values["unit_price"] = 0.0

        return values


class ExtractedTicketInfo(BaseModel):
    ticket_number: int | None
    date: str | None
    time: str | None
    total_price: float | None
    items: List[ExtractedTicketItem]

    def to_db_models(self) -> Tuple[Ticket, List[TicketItem]]:
        """Convert ExtractedTicketInfo to database models"""
        ticket = Ticket(
            ticket_number=self.ticket_number,
            date=self.date,
            time=self.time,
            total_price=self.total_price,
        )

        ticket_items = [
            TicketItem(
                name=item.name,
                quantity=item.quantity,
                total_price=item.total_price,
                unit_price=item.unit_price,
            )
            for item in self.items
        ]

        return ticket, ticket_items
