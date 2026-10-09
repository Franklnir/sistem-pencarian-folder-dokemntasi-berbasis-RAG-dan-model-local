import os
import time
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Tuple

from app.config import settings, canonicalize_path, is_allowed_file
from app.database.models import FileRecord, ChunkRecord
from app.database.repository import get_repository
from app.extractors.registry import ExtractorRegistry
from app.chunking.chunker import DocumentChunker
from app.embedding.model import get_embedding_manager
from app.ingestion.hashing import compute_sha256
from app.ingestion.queue import IngestionJob, get_queue
from app.ingestion.events import get_event_bus

logger = logging.getLogger("ai_file_search.pipeline")


class IngestionPipeline:
    def __init__(self):
        self.repo = get_repository()
        self.chunker = DocumentChunker()
        self.embedder = get_embedding_manager()
        self.stability_window = settings.FILE_STABILITY_MS / 1000.0

    def check_file_stability(self, path: Path, max_retries: int = 3) -> bool:
        """
        Ensures a file has finished being written by an external program.
        Bounded retry: max 3 attempts.
        """
        for attempt in range(max_retries):
            try:
                stat1 = path.stat()
                size1, mtime1 = stat1.st_size, stat1.st_mtime
                # If the file hasn't been modified in the last 5 seconds, it's already stable
                if (time.time() - mtime1) > 5.0:
                    return True

                time.sleep(self.stability_window)
                stat2 = path.stat()
                size2, mtime2 = stat2.st_size, stat2.st_mtime

                if size1 == size2 and mtime1 == mtime2:
                    return True
            except OSError as e:
                logger.warning(f"File locked or inaccessible ({path.name}): {e} (attempt {attempt + 1})")
                time.sleep(0.5)

        return False

    def process_job(self, job: IngestionJob):
        start_time = time.time()
        file_path = Path(job.path)

        try:
            if job.event_type == "DELETE":
                self._handle_delete(job.path)
                duration_ms = (time.time() - start_time) * 1000.0
                get_queue().mark_completed(job.job_id, success=True, duration_ms=duration_ms)
                return

            if job.event_type == "MOVE":
                if job.dest_path:
                    self._handle_move(job.path, job.dest_path)
                    duration_ms = (time.time() - start_time) * 1000.0
                    get_queue().mark_completed(job.job_id, success=True, duration_ms=duration_ms)
                    return

            # Check if file exists
            if not file_path.exists() or not file_path.is_file():
                self._handle_delete(job.path)
                duration_ms = (time.time() - start_time) * 1000.0
                get_queue().mark_completed(job.job_id, success=True, duration_ms=duration_ms)
                return

            # Validate extension and size
            if not is_allowed_file(job.path):
                ext = file_path.suffix.lower()
                error_code = "UNSUPPORTED_EXTENSION" if ext not in settings.ALLOWED_EXTENSIONS else "FILE_TOO_LARGE"
                self._record_failure(job.path, error_code, f"File rejected: {error_code}")
                duration_ms = (time.time() - start_time) * 1000.0
                get_queue().mark_completed(job.job_id, success=False, duration_ms=duration_ms, error_code=error_code)
                return

            # Stability check
            if not self.check_file_stability(file_path):
                self._record_failure(job.path, "FILE_LOCKED", "File remained unstable or locked after retries.")
                duration_ms = (time.time() - start_time) * 1000.0
                get_queue().mark_completed(job.job_id, success=False, duration_ms=duration_ms, error_code="FILE_LOCKED")
                return

            # SHA-256
            content_hash = compute_sha256(job.path)
            stat = file_path.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            size_bytes = stat.st_size

            existing_file = self.repo.get_file_by_path(job.path)

            if existing_file:
                # MODIFY or REINDEX
                if existing_file.content_hash == content_hash and job.event_type != "REINDEX":
                    # Hash unchanged: update timestamp/metadata only, skip extraction/embedding
                    logger.info(f"Skipping re-embedding for unchanged hash: {file_path.name}")
                    existing_file.modified_at = mtime
                    existing_file.size_bytes = size_bytes
                    self.repo.upsert_file(existing_file)
                    duration_ms = (time.time() - start_time) * 1000.0
                    get_queue().mark_completed(job.job_id, success=True, duration_ms=duration_ms)
                    return
                file_id = existing_file.id
                self.repo.update_file_status(file_id, "PROCESSING")
            else:
                # CREATE
                # First check if another file with this hash was just moved
                match_hash = self.repo.get_file_by_hash(content_hash)
                if match_hash and not Path(match_hash.path).exists():
                    logger.info(f"Detected file rename/move by hash match: {match_hash.filename} -> {file_path.name}")
                    self.repo.update_file_path(match_hash.id, job.path, file_path.name)
                    duration_ms = (time.time() - start_time) * 1000.0
                    get_queue().mark_completed(job.job_id, success=True, duration_ms=duration_ms)
                    return

                new_file = FileRecord(
                    path=job.path,
                    filename=file_path.name,
                    extension=file_path.suffix.lower(),
                    size_bytes=size_bytes,
                    modified_at=mtime,
                    content_hash=content_hash,
                    status="PROCESSING"
                )
                file_id = self.repo.upsert_file(new_file)

            # Ingestion: Extraction -> Chunking -> Embedding
            self._ingest_content(file_id, job.path, content_hash, size_bytes, mtime)
            duration_ms = (time.time() - start_time) * 1000.0
            get_queue().mark_completed(job.job_id, success=True, duration_ms=duration_ms)

        except Exception as e:
            logger.error(f"Error processing {job.path}: {e}", exc_info=True)
            self._record_failure(job.path, "PROCESSING_FAILED", str(e))
            duration_ms = (time.time() - start_time) * 1000.0
            get_queue().mark_completed(job.job_id, success=False, duration_ms=duration_ms, error_code="PROCESSING_FAILED")

    def _ingest_content(self, file_id: int, file_path_str: str, content_hash: str, size_bytes: int, mtime: datetime):
        path = Path(file_path_str)
        # 1. Extraction
        try:
            sections = ExtractorRegistry.extract(file_path_str)
        except Exception as e:
            self.repo.update_file_status(file_id, "FAILED", f"EXTRACTION_FAILED: {str(e)}")
            raise

        # 2. Chunking
        chunks = self.chunker.chunk_extracted_sections(sections)
        if not chunks:
            # File might be empty of text
            self.repo.replace_chunks(file_id, [])
            self.repo.update_file_indexed(file_id, content_hash, size_bytes, mtime)
            return

        # 3. Batch Embedding
        chunk_texts = [c.text for c in chunks]
        embeddings = self.embedder.encode_batch(chunk_texts)

        # 4. Save to DB transactionally
        chunk_records = []
        for i, c in enumerate(chunks):
            chunk_records.append(ChunkRecord(
                file_id=file_id,
                page_no=c.page_no,
                chunk_index=c.chunk_index,
                text=c.text,
                embedding=embeddings[i],
                token_count=c.token_count
            ))

        self.repo.replace_chunks(file_id, chunk_records)
        self.repo.update_file_indexed(file_id, content_hash, size_bytes, mtime)
        logger.info(f"Successfully indexed '{path.name}': {len(chunk_records)} chunks.")
        get_event_bus().emit("file_indexed", {
            "file_id": file_id,
            "filename": path.name,
            "path": file_path_str,
            "extension": path.suffix.lower(),
            "size_bytes": size_bytes,
            "chunks": len(chunk_records),
            "status": "INDEXED"
        })

    def _handle_move(self, old_path: str, new_path: str):
        c_old = canonicalize_path(old_path)
        c_new = canonicalize_path(new_path)
        new_p = Path(c_new)

        existing = self.repo.get_file_by_path(c_old)
        if existing:
            if new_p.exists() and is_allowed_file(c_new):
                new_hash = compute_sha256(c_new)
                if new_hash == existing.content_hash:
                    # Update path only, no re-embedding
                    logger.info(f"Renamed {existing.filename} -> {new_p.name} with identical hash. Updating metadata.")
                    self.repo.update_file_path(existing.id, c_new, new_p.name)
                    get_event_bus().emit("file_renamed", {
                        "file_id": existing.id,
                        "old_filename": existing.filename,
                        "filename": new_p.name,
                        "path": c_new
                    })
                    return

            # If hash differs or new file isn't allowed, delete old and re-process new
            self.repo.delete_file(existing.id)
            get_event_bus().emit("file_deleted", {
                "file_id": existing.id,
                "filename": existing.filename,
                "path": existing.path
            })

        if new_p.exists() and is_allowed_file(c_new):
            get_queue().push("CREATE", c_new)

    def _handle_delete(self, path: str):
        c_path = canonicalize_path(path)
        existing = self.repo.get_file_by_path(c_path)
        if existing:
            logger.info(f"Deleting indexed file record and chunks: {existing.filename}")
            self.repo.delete_file(existing.id)
            get_event_bus().emit("file_deleted", {
                "file_id": existing.id,
                "filename": existing.filename,
                "path": existing.path
            })

    def _record_failure(self, path: str, code: str, msg: str):
        c_path = canonicalize_path(path)
        p = Path(c_path)
        existing = self.repo.get_file_by_path(c_path)
        now = datetime.now(timezone.utc)
        if existing:
            self.repo.update_file_status(existing.id, "FAILED", f"{code}: {msg}")
        else:
            rec = FileRecord(
                path=c_path,
                filename=p.name,
                extension=p.suffix.lower(),
                size_bytes=p.stat().st_size if p.exists() else 0,
                modified_at=datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc) if p.exists() else now,
                content_hash="0" * 64,
                status="FAILED",
                error_message=f"{code}: {msg}"
            )
            self.repo.upsert_file(rec)
