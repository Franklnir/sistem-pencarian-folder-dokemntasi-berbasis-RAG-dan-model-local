import os
from pathlib import Path
from typing import Set
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000
    DATABASE_URL: str = "postgresql://postgres:postgres@127.0.0.1:5432/ai_file_search"
    EMBEDDING_MODEL: str = "paraphrase-multilingual-MiniLM-L12-v2"
    EMBEDDING_DEVICE: str = "cpu"
    SEARCH_TOP_K_DEFAULT: int = 5
    SEARCH_TOP_K_MAX: int = 50
    WATCH_DEBOUNCE_MS: int = 1000
    FILE_STABILITY_MS: int = 1500
    MAX_FILE_SIZE_MB: int = 100
    INDEX_WORKERS: int = 1
    LOG_LEVEL: str = "INFO"
    DATA_DIR: str = str(Path(__file__).resolve().parent.parent / "data")

    # Local Offline LLM (Default: Qwen 2.5 0.5B Ultra-Fast ~468MB, or 1.5B)
    LLM_MODEL_NAME: str = "qwen2.5-0.5b-instruct-q4_k_m.gguf"
    LLM_REPO_ID: str = "Qwen/Qwen2.5-0.5B-Instruct-GGUF"
    LLM_MODEL_DIR: str = str(Path(__file__).resolve().parent.parent / "data" / "models")
    LLM_CONTEXT_SIZE: int = 4096
    LLM_THREADS: int = 4

    ALLOWED_EXTENSIONS: Set[str] = {".pdf", ".docx", ".txt"}


settings = Settings()

# Ensure DATA_DIR and LLM_MODEL_DIR exist
os.makedirs(settings.DATA_DIR, exist_ok=True)
os.makedirs(settings.LLM_MODEL_DIR, exist_ok=True)


def canonicalize_path(path_str: str) -> str:
    """Canonicalize a path for Windows consistency: absolute, resolved, uniform separators."""
    if not path_str or not isinstance(path_str, str):
        return ""
    p = Path(path_str.strip()).resolve()
    # Normalize Windows drive letter to uppercase for consistent DB primary keys/lookups
    normalized = str(p)
    if len(normalized) >= 2 and normalized[1] == ":":
        normalized = normalized[0].upper() + normalized[1:]
    return normalized


def is_allowed_file(path_str: str) -> bool:
    """Check if the file has an allowed extension and is within the size limit."""
    p = Path(path_str)
    ext = p.suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        return False
    try:
        if p.exists() and p.is_file():
            size_mb = p.stat().st_size / (1024 * 1024)
            if size_mb > settings.MAX_FILE_SIZE_MB:
                return False
    except OSError:
        return False
    return True


def is_critical_system_directory(path_str: str) -> bool:
    """Validate that path is not a critical Windows system directory."""
    canon = canonicalize_path(path_str).lower()
    system_dirs = [
        "c:\\windows",
        "c:\\program files",
        "c:\\program files (x86)",
        "c:\\system volume information",
        "c:\\$recycle.bin",
        "c:\\boot",
    ]
    for sys_dir in system_dirs:
        if canon == sys_dir or canon.startswith(sys_dir + "\\"):
            return True
    return False
