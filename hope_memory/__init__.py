"""
Hope Memory - Human-like Cognitive Memory System for AI

Features:
- 6-layer cognitive architecture (Working, Short-term, Long-term, Emotional, Relational, Associative)
- Silent Hope Protocol (SHP) for lightning-fast communication
- Memory Chain references (zero context rebuild)
- Connection pooling for databases

Created by: Hope + Máté Róbert
License: MIT

Example:
    from hope_memory import HopeMemory

    memory = HopeMemory()
    memory.think("Important information", importance=0.8)
    results = memory.remember("information")
"""

__version__ = "0.1.0"
__author__ = "Hope + Máté Róbert"

from .cognitive import HopeMemory, Thought, Person
from .cache import HopeCache, MemoryChain, get_cache, get_chain

__all__ = [
    "HopeMemory",
    "Thought",
    "Person",
    "HopeCache",
    "MemoryChain",
    "get_cache",
    "get_chain",
]
