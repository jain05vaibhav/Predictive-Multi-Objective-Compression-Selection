"""
Stage 5 Compression Adapter (Backwards Compatibility Module)

Re-exports CompressionStage and delta encoding helpers from edge.stage6_compression
to maintain 100% compatibility with existing test suites and imports.
"""

from edge.stage6_compression import (
    CompressionStage,
    delta_encode_bytes,
    delta_decode_bytes,
    LZ4_AVAILABLE,
    ZSTD_AVAILABLE
)

__all__ = [
    "CompressionStage",
    "delta_encode_bytes",
    "delta_decode_bytes",
    "LZ4_AVAILABLE",
    "ZSTD_AVAILABLE"
]
