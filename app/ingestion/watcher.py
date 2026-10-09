import os
import time
import logging
import threading
from pathlib import Path
from typing import Dict, Optional, Set, Any

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from app.config import settings, canonicalize_path, is_allowed_file
from app.database.repository import get_repository
from app.ingestion.queue import get_queue
from app.ingestion.pipeline import IngestionPipeline
from app.ingestion.events import get_event_bus

logger = logging.getLogger("ai_file_search.watcher")


class DocumentEventHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self.queue = get_queue()

    def _should_ignore(self, path_str: str) -> bool:
        p = Path(path_str)
        name = p.name
        # Ignore temporary Windows / office files or hidden dotfiles
        if name.startswith("~$") or name.startswith(".") or name.endswith(".tmp"):
            return True
        if p.suffix.lower() not in settings.ALLOWED_EXTENSIONS:
            return True
        return False

    def on_created(self, event: FileSystemEvent):
        if event.is_directory or self._should_ignore(event.src_path):
            return
        logger.debug(f"FS CREATE detected: {event.src_path}")
        self.queue.push("CREATE", event.src_path)
        get_event_bus().emit("file_detected", {
            "type": "CREATE",
            "path": event.src_path,
            "filename": Path(event.src_path).name
        })

    def on_modified(self, event: FileSystemEvent):
        if event.is_directory or self._should_ignore(event.src_path):
            return
        logger.debug(f"FS MODIFY detected: {event.src_path}")
        self.queue.push("MODIFY", event.src_path)
        get_event_bus().emit("file_detected", {
            "type": "MODIFY",
            "path": event.src_path,
            "filename": Path(event.src_path).name
        })

    def on_deleted(self, event: FileSystemEvent):
        if event.is_directory or self._should_ignore(event.src_path):
            return
        logger.debug(f"FS DELETE detected: {event.src_path}")
        self.queue.push("DELETE", event.src_path)
        get_event_bus().emit("file_detected", {
            "type": "DELETE",
            "path": event.src_path,
            "filename": Path(event.src_path).name
        })

    def on_moved(self, event: FileSystemEvent):
        if event.is_directory:
            return
        src_ignore = self._should_ignore(event.src_path)
        dest_ignore = self._should_ignore(event.dest_path)
        if src_ignore and dest_ignore:
            return
        logger.debug(f"FS MOVE detected: {event.src_path} -> {event.dest_path}")
        self.queue.push("MOVE", event.src_path, dest_path=event.dest_path)
        get_event_bus().emit("file_detected", {
            "type": "MOVE",
            "path": event.src_path,
            "dest_path": event.dest_path,
            "filename": Path(event.dest_path).name
        })


class WatcherService:
    def __init__(self):
        self.observer: Optional[Observer] = None
        self.watched_paths: Dict[str, Any] = {}
        self.handler = DocumentEventHandler()
        self.pipeline = IngestionPipeline()
        self.is_running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self):
        if self.is_running:
            return

        self._stop_event.clear()
        self.observer = Observer()
        self.watched_paths.clear()

        # Start worker thread
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

        # Sync folders from database
        self.sync_monitored_folders()

        self.observer.start()
        self.is_running = True
        logger.info("WatcherService and ingestion worker thread started.")

    def stop(self):
        if not self.is_running:
            return

        self._stop_event.set()
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=2.0)
            self.observer = None

        if self._worker_thread:
            self._worker_thread.join(timeout=2.0)
            self._worker_thread = None

        self.is_running = False
        logger.info("WatcherService stopped.")

    def sync_monitored_folders(self):
        """Re-sync folders being watched with the monitored_folders database table."""
        repo = get_repository()
        folders = repo.get_folders()
        active_paths: Set[str] = set()

        for folder in folders:
            if folder.enabled and Path(folder.path).exists():
                canon = canonicalize_path(folder.path)
                active_paths.add(canon)
                if canon not in self.watched_paths and self.observer:
                    try:
                        watch = self.observer.schedule(self.handler, canon, recursive=True)
                        self.watched_paths[canon] = watch
                        logger.info(f"Scheduled watcher for folder: {canon}")
                        # Perform initial scan of existing files
                        self._scan_existing_files(canon)
                    except Exception as e:
                        logger.error(f"Failed to watch {canon}: {e}")

        # Remove unwatched
        for canon, watch in list(self.watched_paths.items()):
            if canon not in active_paths:
                try:
                    if self.observer:
                        self.observer.unschedule(watch)
                    del self.watched_paths[canon]
                    logger.info(f"Unscheduled watcher for: {canon}")
                except Exception as e:
                    logger.warning(f"Error unscheduling {canon}: {e}")

    def _scan_existing_files(self, folder_path: str):
        """Scans a newly added folder and queues files that need ingestion in the background."""
        def _bg_scan():
            p = Path(folder_path)
            if not p.exists() or not p.is_dir():
                return

            logger.info(f"Scanning folder for documents: {folder_path}")
            queue = get_queue()
            count = 0
            ignore_dirs = {".git", ".svn", "node_modules", "__pycache__", "venv", ".venv", "env", "appdata", "local settings"}
            try:
                for root, dirs, files in os.walk(p):
                    dirs[:] = [d for d in dirs if not d.startswith(".") and d.lower() not in ignore_dirs]
                    for file_name in files:
                        if file_name.startswith("~$") or file_name.startswith(".") or file_name.endswith(".tmp"):
                            continue
                        full_path = os.path.join(root, file_name)
                        if is_allowed_file(full_path):
                            queue.push("CREATE", full_path)
                            count += 1
            except Exception as e:
                logger.warning(f"Error while scanning folder {folder_path}: {e}")
            logger.info(f"Enqueued {count} files from '{folder_path}'.")

        threading.Thread(target=_bg_scan, daemon=True, name=f"scan_{Path(folder_path).name}").start()

    def _worker_loop(self):
        queue = get_queue()
        while not self._stop_event.is_set():
            job = queue.pop_ready()
            if job:
                try:
                    self.pipeline.process_job(job)
                except Exception as e:
                    logger.error(f"Worker exception processing job {job.job_id}: {e}", exc_info=True)
            else:
                time.sleep(0.1)


_watcher_instance: Optional[WatcherService] = None


def get_watcher() -> WatcherService:
    global _watcher_instance
    if _watcher_instance is None:
        _watcher_instance = WatcherService()
    return _watcher_instance
