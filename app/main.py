import time
import uuid
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from app.config import settings
from app.api import (
    health_router,
    folders_router,
    files_router,
    search_router,
    indexing_router,
    chat_router
)
from app.embedding.model import get_embedding_manager
from app.database.repository import get_repository
from app.ingestion.watcher import get_watcher

# Configure Structured Logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] [req:%(request_id)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("ai_file_search")

# Custom log filter to inject request_id
class RequestIdFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return True

for handler in logging.root.handlers:
    handler.addFilter(RequestIdFilter())


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup:
    logger.info("Initializing AI File Search backend...")
    get_repository()
    get_embedding_manager()
    watcher = get_watcher()
    watcher.start()
    logger.info("AI File Search initialized and ready.")
    yield
    # Shutdown:
    logger.info("Shutting down AI File Search backend...")
    watcher.stop()
    logger.info("AI File Search stopped cleanly.")


app = FastAPI(
    title="AI File Search",
    description="Local semantic and hybrid document retrieval for Windows",
    version="1.0.0",
    lifespan=lifespan
)

# Request ID & Audit Logging Middleware (Section 19)
@app.middleware("http")
async def request_id_and_logging_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
    start_time = time.perf_counter()

    # Pass request_id via state
    request.state.request_id = req_id

    response = await call_next(request)

    duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
    response.headers["X-Request-ID"] = req_id

    logger.info(
        f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms}ms)",
        extra={"request_id": req_id}
    )
    return response


# Static and Templates
app_dir = Path(__file__).resolve().parent
static_dir = app_dir / "static"
templates_dir = app_dir / "templates"

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(templates_dir))


# API Routers
app.include_router(health_router)
app.include_router(folders_router)
app.include_router(files_router)
app.include_router(search_router)
app.include_router(indexing_router)
app.include_router(chat_router)


# Web UI
@app.get("/", response_class=HTMLResponse)
def index_page(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    return templates.TemplateResponse(request=request, name="settings.html")




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=False
    )
