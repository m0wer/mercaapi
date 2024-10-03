from fastapi import FastAPI, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select
from app.database import create_db_and_tables, get_session
from app.models import Product, Category
import time

app = FastAPI()

# API router
api_router = FastAPI()


@api_router.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = time.perf_counter() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


@api_router.on_event("startup")
def on_startup():
    create_db_and_tables()


@api_router.get("/products")
def get_products(
    skip: int = 0, limit: int = 100, session: Session = Depends(get_session)
):
    products = session.exec(select(Product).offset(skip).limit(limit)).all()
    return products


@api_router.get("/products/{product_id}")
def get_product(product_id: str, session: Session = Depends(get_session)):
    product = session.exec(select(Product).where(Product.id == product_id)).first()
    if not product:
        return {"error": "Product not found"}
    return product


@api_router.get("/categories")
def get_categories(
    skip: int = 0, limit: int = 100, session: Session = Depends(get_session)
):
    categories = session.exec(select(Category).offset(skip).limit(limit)).all()
    return categories


# Mount the API router
app.mount("/api", api_router)

# Serve static files
app.mount("/", StaticFiles(directory="static", html=True), name="static")


# Redirect /api to /api/docs
@app.get("/api")
async def redirect_to_docs():
    return RedirectResponse(url="/api/docs")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=80)
