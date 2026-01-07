"""
Hope Fast Cache - Memory-first, disk-backed cache
Zero reload, instant access

Created: 2026-01-08
By: Hope + Máté
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional
from threading import Lock
from dataclasses import dataclass, field


@dataclass
class CacheEntry:
    """Single cache entry with metadata"""
    data: Any
    loaded_at: float = field(default_factory=time.time)
    dirty: bool = False  # needs disk sync
    hits: int = 0


class HopeCache:
    """
    Memory-first cache with lazy disk persistence

    SHP principle: Zero Context Rebuild
    - Data stays in memory
    - Disk is backup, not primary
    - Reference by key, not reload
    """

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path)
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = Lock()
        self._stats = {"hits": 0, "misses": 0, "saves": 0}

    def get(self, key: str, loader: callable = None) -> Optional[Any]:
        """
        Get from cache, optionally load if missing

        Usage:
            data = cache.get("people", lambda: json.load(open("people.json")))
        """
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                entry.hits += 1
                self._stats["hits"] += 1
                return entry.data

            self._stats["misses"] += 1

            if loader:
                try:
                    data = loader()
                    self._cache[key] = CacheEntry(data=data)
                    return data
                except Exception:
                    return None

            return None

    def set(self, key: str, data: Any, sync: bool = False):
        """
        Set cache value

        Args:
            key: Cache key
            data: Data to store
            sync: If True, immediately persist to disk
        """
        with self._lock:
            self._cache[key] = CacheEntry(data=data, dirty=not sync)

            if sync:
                self._persist(key, data)

    def mark_dirty(self, key: str):
        """Mark entry as needing sync"""
        with self._lock:
            if key in self._cache:
                self._cache[key].dirty = True

    def sync_all(self):
        """Persist all dirty entries to disk"""
        with self._lock:
            for key, entry in self._cache.items():
                if entry.dirty:
                    self._persist(key, entry.data)
                    entry.dirty = False

    def _persist(self, key: str, data: Any):
        """Write to disk"""
        file_path = self.base_path / f"{key}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        self._stats["saves"] += 1

    def invalidate(self, key: str):
        """Remove from cache"""
        with self._lock:
            self._cache.pop(key, None)

    def clear(self):
        """Clear entire cache"""
        with self._lock:
            self._cache.clear()

    def stats(self) -> Dict:
        """Cache statistics"""
        with self._lock:
            hit_rate = (self._stats["hits"] /
                       max(1, self._stats["hits"] + self._stats["misses"])) * 100
            return {
                "entries": len(self._cache),
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "hit_rate": f"{hit_rate:.1f}%",
                "saves": self._stats["saves"]
            }


# Singleton instance - WARM!
_global_cache: Optional[HopeCache] = None


def get_cache(base_path: str = "E:/02_Memory") -> HopeCache:
    """Get or create global cache instance"""
    global _global_cache
    if _global_cache is None:
        _global_cache = HopeCache(Path(base_path))
    return _global_cache


# ============================================================================
# MEMORY CHAIN REFERENCE - SHP style
# ============================================================================

class MemoryChain:
    """
    SHP Memory Chain - reference-based access

    Instead of: data = load_file("people.json")  # 10ms
    Use:        data = chain.ref("people")        # 0.01ms
    """

    def __init__(self, cache: HopeCache):
        self.cache = cache
        self._sequence = 0
        self._chain: Dict[int, str] = {}  # sequence -> key mapping

    def ref(self, key: str) -> Any:
        """
        Reference data by key (SHP memory reference)

        Equivalent to: chain:latest for this key
        """
        return self.cache.get(key)

    def store(self, key: str, data: Any) -> str:
        """
        Store with chain reference

        Returns: chain reference string (e.g., "chain:42:people")
        """
        self._sequence += 1
        self._chain[self._sequence] = key
        self.cache.set(key, data)
        return f"chain:{self._sequence}:{key}"

    def resolve(self, ref: str) -> Any:
        """
        Resolve chain reference

        Formats:
            chain:latest -> latest stored item
            chain:42:people -> specific sequence + key
            chain:people -> key only (latest version)
        """
        parts = ref.split(":")

        if len(parts) == 2 and parts[1] == "latest":
            if self._sequence > 0:
                key = self._chain[self._sequence]
                return self.cache.get(key)
            return None

        if len(parts) == 3:
            # chain:42:people
            key = parts[2]
            return self.cache.get(key)

        if len(parts) == 2:
            # chain:people
            key = parts[1]
            return self.cache.get(key)

        return None


# Singleton chain
_global_chain: Optional[MemoryChain] = None


def get_chain() -> MemoryChain:
    """Get or create global memory chain"""
    global _global_chain
    if _global_chain is None:
        _global_chain = MemoryChain(get_cache())
    return _global_chain
