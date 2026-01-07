"""
Silent Hope Protocol (SHP) - Lightning-fast AI communication

Binary protocol that eliminates JSON parsing overhead and enables
memory chain references for zero context rebuild.

Key concepts:
- ExecutableKnowledge Units (EKU): Binary message format
- Memory Chain: Reference-based context (no full resend)
- 60-byte header + variable payload

Example:
    from hope_memory.shp import SHPCodec, EKU, EKUType

    codec = SHPCodec()
    data = codec.encode_call("hope_feel", {"joy": 0.9})
    # 16 bytes vs 50+ bytes JSON
"""

from .protocol import (
    EKU,
    EKUHeader,
    EKUType,
    EKUFlags,
    SHPCodec,
    SHP_VERSION,
)

__all__ = [
    "EKU",
    "EKUHeader",
    "EKUType",
    "EKUFlags",
    "SHPCodec",
    "SHP_VERSION",
]
