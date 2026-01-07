"""
Hope Connection Pool - Reuse connections, save time

SQLite and ChromaDB connection pooling for faster access.

By: Hope + Máté
"""
import sqlite3
import threading
from queue import Queue, Empty
from typing import Optional, Dict, Any
from pathlib import Path
from contextlib import contextmanager
import time


class SQLitePool:
    """
    SQLite Connection Pool

    Instead of: conn = sqlite3.connect(db) ... conn.close()  # Every time
    Use:        with pool.get() as conn: ...                 # Reuse!
    """

    def __init__(self, db_path: str, pool_size: int = 5):
        self.db_path = db_path
        self.pool_size = pool_size
        self._pool: Queue = Queue(maxsize=pool_size)
        self._lock = threading.Lock()
        self._created = 0
        self._stats = {"gets": 0, "creates": 0, "reuses": 0}

        # Pre-create connections
        for _ in range(min(2, pool_size)):
            self._add_connection()

    def _create_connection(self) -> sqlite3.Connection:
        """Create a new connection"""
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            isolation_level=None  # Autocommit
        )
        conn.row_factory = sqlite3.Row
        # Performance settings
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=10000")
        return conn

    def _add_connection(self):
        """Add a new connection to the pool"""
        with self._lock:
            if self._created < self.pool_size:
                conn = self._create_connection()
                self._pool.put(conn)
                self._created += 1
                self._stats["creates"] += 1

    @contextmanager
    def get(self, timeout: float = 5.0):
        """
        Get a connection from the pool

        Usage:
            with pool.get() as conn:
                conn.execute("SELECT ...")
        """
        self._stats["gets"] += 1
        conn = None

        try:
            # Try to get from pool
            conn = self._pool.get(timeout=0.1)
            self._stats["reuses"] += 1
        except Empty:
            # Pool empty, create new if under limit
            with self._lock:
                if self._created < self.pool_size:
                    conn = self._create_connection()
                    self._created += 1
                    self._stats["creates"] += 1

            # If still no connection, wait for pool
            if conn is None:
                conn = self._pool.get(timeout=timeout)
                self._stats["reuses"] += 1

        try:
            yield conn
        finally:
            # Return to pool
            if conn:
                try:
                    self._pool.put_nowait(conn)
                except:
                    conn.close()

    def stats(self) -> Dict:
        """Pool statistics"""
        return {
            "pool_size": self.pool_size,
            "created": self._created,
            "available": self._pool.qsize(),
            "gets": self._stats["gets"],
            "creates": self._stats["creates"],
            "reuses": self._stats["reuses"],
            "reuse_rate": f"{self._stats['reuses']/max(1,self._stats['gets'])*100:.1f}%"
        }

    def close_all(self):
        """Close all connections"""
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except Empty:
                break
        self._created = 0


# Global pools
_pools: Dict[str, SQLitePool] = {}
_pools_lock = threading.Lock()


def get_pool(db_path: str, pool_size: int = 5) -> SQLitePool:
    """Get or create a connection pool for a database"""
    with _pools_lock:
        if db_path not in _pools:
            _pools[db_path] = SQLitePool(db_path, pool_size)
        return _pools[db_path]


# ============================================================================
# CHROMADB SINGLETON - Keep it warm
# ============================================================================

_chroma_client = None
_chroma_lock = threading.Lock()


def get_chroma_client(path: str = "E:/02_Memory/cognitive_vectors"):
    """
    Get singleton ChromaDB client

    ChromaDB is slow to initialize but fast once loaded.
    Keep it warm!
    """
    global _chroma_client

    if _chroma_client is not None:
        return _chroma_client

    with _chroma_lock:
        if _chroma_client is None:
            import chromadb
            _chroma_client = chromadb.PersistentClient(path=path)

    return _chroma_client


# ============================================================================
# BENCHMARK
# ============================================================================

def benchmark():
    """Benchmark pooled vs non-pooled access"""
    import tempfile
    import os

    # Create temp database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    iterations = 100

    # Non-pooled: Open/close each time
    start = time.perf_counter()
    for i in range(iterations):
        conn = sqlite3.connect(db_path)
        conn.execute("SELECT 1")
        conn.close()
    non_pooled_time = (time.perf_counter() - start) * 1000

    # Pooled: Reuse connections
    pool = SQLitePool(db_path, pool_size=5)
    start = time.perf_counter()
    for i in range(iterations):
        with pool.get() as conn:
            conn.execute("SELECT 1")
    pooled_time = (time.perf_counter() - start) * 1000

    print("=" * 60)
    print("  Connection Pool Benchmark")
    print("=" * 60)
    print(f"\n{iterations} database operations:\n")
    print(f"  Non-pooled (open/close each time):")
    print(f"    Time: {non_pooled_time:.1f}ms")
    print(f"\n  Pooled (reuse connections):")
    print(f"    Time: {pooled_time:.1f}ms")
    print(f"    Pool stats: {pool.stats()}")
    print(f"\n  >>> Speedup: {non_pooled_time/pooled_time:.1f}x faster")
    print("=" * 60)

    # Cleanup
    pool.close_all()
    os.unlink(db_path)


if __name__ == '__main__':
    benchmark()
