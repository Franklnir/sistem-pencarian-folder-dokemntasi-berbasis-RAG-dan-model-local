import time
import uuid
import logging
from typing import Optional, Dict
from dataclasses import dataclass
from collections import OrderedDict
import threading

from app.config import settings, canonicalize_path

logger = logging.getLogger("ai_file_search.queue")


@dataclass
class IngestionJob:
    job_id: str
    path: str
    event_type: str  # CREATE, MODIFY, DELETE, MOVE, REINDEX
    dest_path: Optional[str] = None
    created_at: float = 0.0
    status: str = "QUEUED"  # QUEUED, PROCESSING, DONE, FAILED
    error_code: Optional[str] = None
    duration_ms: Optional[float] = None


class DebouncedIngestionQueue:
    """
    Thread-safe debouncing queue that coalesces duplicate filesystem events
    within WATCH_DEBOUNCE_MS before yielding to workers.
    """

    def __init__(self, debounce_ms: int = settings.WATCH_DEBOUNCE_MS):
        self.debounce_sec = debounce_ms / 1000.0
        self._lock = threading.Lock()
        self._pending_events: Dict[str, IngestionJob] = OrderedDict()
        self._all_jobs: Dict[str, IngestionJob] = {}

    def push(self, event_type: str, path: str, dest_path: Optional[str] = None) -> str:
        canon_path = canonicalize_path(path)
        canon_dest = canonicalize_path(dest_path) if dest_path else None
        now = time.time()

        with self._lock:
            # If an event already exists for this path, coalesce
            existing = self._pending_events.get(canon_path)
            if existing:
                # E.g. multiple MODIFY events coalesce into one with latest timestamp
                existing.created_at = now
                if event_type == "DELETE":
                    existing.event_type = "DELETE"
                elif event_type == "MOVE":
                    existing.event_type = "MOVE"
                    existing.dest_path = canon_dest
                return existing.job_id

            job_id = f"job_{uuid.uuid4().hex[:12]}"
            job = IngestionJob(
                job_id=job_id,
                path=canon_path,
                event_type=event_type,
                dest_path=canon_dest,
                created_at=now,
                status="QUEUED"
            )
            self._pending_events[canon_path] = job
            self._all_jobs[job_id] = job
            return job_id

    def pop_ready(self) -> Optional[IngestionJob]:
        """Pops the oldest job whose debounce window has elapsed."""
        now = time.time()
        with self._lock:
            for path, job in list(self._pending_events.items()):
                if now - job.created_at >= self.debounce_sec:
                    del self._pending_events[path]
                    job.status = "PROCESSING"
                    return job
        return None

    def mark_completed(self, job_id: str, success: bool, duration_ms: float, error_code: Optional[str] = None):
        with self._lock:
            job = self._all_jobs.get(job_id)
            if job:
                job.status = "DONE" if success else "FAILED"
                job.duration_ms = duration_ms
                job.error_code = error_code

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending_events)

    def get_job(self, job_id: str) -> Optional[IngestionJob]:
        with self._lock:
            return self._all_jobs.get(job_id)


_queue_instance: Optional[DebouncedIngestionQueue] = None


def get_queue() -> DebouncedIngestionQueue:
    global _queue_instance
    if _queue_instance is None:
        _queue_instance = DebouncedIngestionQueue()
    return _queue_instance
