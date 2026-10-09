import hashlib
from pathlib import Path


def compute_sha256(file_path: str, chunk_size: int = 65536) -> str:
    """
    Computes SHA-256 hash of a file reading in 64KB blocks.
    Ensures low memory usage even for 100MB files.
    """
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)

    return hasher.hexdigest()
