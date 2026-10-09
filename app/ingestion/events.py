import time
import queue
import logging
import threading
from typing import Dict, Any, Set, Optional

logger = logging.getLogger("ai_file_search.events")


class SyncEventBus:
    """
    Thread-safe event broadcaster for real-time synchronization between
    local Windows filesystem Watchdog / Ingestion pipeline and the web frontend (SSE).
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._subscribers: Set[queue.Queue] = set()

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=200)
        with self._lock:
            self._subscribers.add(q)
            logger.debug(f"New SSE subscriber connected. Total subscribers: {len(self._subscribers)}")
        return q

    def unsubscribe(self, q: queue.Queue):
        with self._lock:
            self._subscribers.discard(q)
            logger.debug(f"SSE subscriber disconnected. Remaining: {len(self._subscribers)}")

    def emit(self, event_type: str, data: Dict[str, Any]):
        """Emit an event to all connected clients."""
        payload = {
            "event": event_type,
            "data": data,
            "timestamp": time.time()
        }
        with self._lock:
            dead_queues = []
            for q in self._subscribers:
                try:
                    q.put_nowait(payload)
                except queue.Full:
                    # Drop oldest or mark as dead
                    try:
                        q.get_nowait()
                        q.put_nowait(payload)
                    except Exception:
                        dead_queues.append(q)
            for dq in dead_queues:
                self._subscribers.discard(dq)


_event_bus: Optional[SyncEventBus] = None
_bus_lock = threading.Lock()


def get_event_bus() -> SyncEventBus:
    global _event_bus
    if _event_bus is None:
        with _bus_lock:
            if _event_bus is None:
                _event_bus = SyncEventBus()
    return _event_bus
