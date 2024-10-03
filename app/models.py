from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List

class Category(SQLModel, table=True):
    id: int = Field(primary_key=True)
    name: str
    parent_id: Optional[int] = Field(default=None, foreign_key="category.id")

class Product(SQLModel, table=True):
    id: str = Field(primary_key=True)
    ean: str
    slug: str
    brand: Optional[str]
    name: str
    price: float
    category_id: int = Field(foreign_key="category.id")
    description: Optional[str]
    origin: Optional[str]
    packaging: Optional[str]
    unit_name: Optional[str]
    unit_size: Optional[float]
    is_variable_weight: bool = False
    is_pack: bool = False
    
    images: List["ProductImage"] = Relationship(back_populates="product")

class ProductImage(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    product_id: str = Field(foreign_key="product.id")
    zoom_url: str
    regular_url: str
    thumbnail_url: str
    perspective: int
    
    product: Product = Relationship(back_populates="images")
