import sys
import time

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from loguru import logger

from app.routers import products, categories, ticket

# Configure loguru
logger.remove()
logger.add(
    sys.stdout, colorize=True, format="<green>{time}</green> <level>{message}</level>"
)

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


# Include routers
api_router.include_router(products.router)
api_router.include_router(categories.router)
api_router.include_router(ticket.router)

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

    uvicorn.run(app, host="0.0.0.0", port=8000)
