"""Thread-safe in-memory cache for complete RAG answers."""

from __future__ import annotations

import threading
import time
from collections import OrderedDict

from src.common.schemas import AnswerResponse


class AnswerCache:
    """TTL cache with a maximum number of entries."""

    def __init__(self, maxsize: int = 256, ttl_seconds: int = 300):
        if maxsize < 1:
            raise ValueError("maxsize must be at least 1")
        if ttl_seconds < 1:
            raise ValueError("ttl_seconds must be at least 1")

        self.maxsize = maxsize
        self.ttl_seconds = ttl_seconds
        self._entries: OrderedDict[
            str, tuple[float, AnswerResponse]
        ] = OrderedDict()
        self._lock = threading.RLock()

    def get(self, key: str) -> AnswerResponse | None:
        """Return a cached response, or None if missing or expired."""
        with self._lock:
            entry = self._entries.get(key)

            if entry is None:
                return None

            expires_at, response = entry

            if time.monotonic() >= expires_at:
                del self._entries[key]
                return None

            # Recently used entries move to the end.
            self._entries.move_to_end(key)

            # Return a copy so callers cannot modify the cached object.
            return response.model_copy(deep=True)

    def set(self, key: str, response: AnswerResponse) -> None:
        """Store a response and evict the oldest entry if necessary."""
        with self._lock:
            self._entries[key] = (
                time.monotonic() + self.ttl_seconds,
                response.model_copy(deep=True),
            )
            self._entries.move_to_end(key)

            while len(self._entries) > self.maxsize:
                self._entries.popitem(last=False)

    def clear(self) -> None:
        """Remove all cached answers."""
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)