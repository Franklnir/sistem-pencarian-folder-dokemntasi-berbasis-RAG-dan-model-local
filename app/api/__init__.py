from app.api.health import router as health_router
from app.api.folders import router as folders_router
from app.api.files import router as files_router
from app.api.search import router as search_router
from app.api.indexing import router as indexing_router
from app.api.chat import chat_router

__all__ = [
    "health_router",
    "folders_router",
    "files_router",
    "search_router",
    "indexing_router",
    "chat_router"
]
