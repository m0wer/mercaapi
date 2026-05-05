import sys
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.routers import categories, products, reports, ticket

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
    logger.info(f"Processed {request.url} in {process_time:.3f} seconds")
    return response


# Include routers
api_router.include_router(products.router)
api_router.include_router(categories.router)
api_router.include_router(ticket.router)
api_router.include_router(reports.router)

# Mount the API router
app.mount("/api", api_router)


# Serve SKILL.md at /SKILL.md
@app.get("/SKILL.md")
async def skill_md():
    return FileResponse(Path(__file__).parent / "SKILL.md", media_type="text/markdown")


# Serve static files
app.mount("/", StaticFiles(directory="static", html=True), name="static")


# Redirect /api to /api/docs
@app.get("/api")
async def redirect_to_docs():
    return RedirectResponse(url="/api/docs")
