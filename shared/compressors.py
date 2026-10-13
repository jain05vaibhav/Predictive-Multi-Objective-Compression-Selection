"""
Shared Compressor Registry & Zero-Copy Buffer Pool (Phase 14)

Provides unified registry for all candidate compressors and decompressors
with transparent fallbacks, fine-grained level configurations, and zero-copy
memory buffer pooling for edge platforms.
"""

import bz2
import zlib
from typing import Dict, Any, Callable, Optional, Tuple, List

# Codec availability checks with clean fallbacks
try:
    import lz4.frame as lz4_frame
    HAS_LZ4 = True
except ImportError:
    lz4_frame = None
    HAS_LZ4 = False

try:
    import zstandard as zstd
    HAS_ZSTD = True
except ImportError:
    zstd = None
    HAS_ZSTD = False

try:
    import snappy
    HAS_SNAPPY = True
except ImportError:
    snappy = None
    HAS_SNAPPY = False


def delta_encode_bytes(raw_bytes: bytes) -> bytes:
    """Computes first-order consecutive differences mod 256."""
    if not raw_bytes:
        return b""
    encoded = bytearray(len(raw_bytes))
    encoded[0] = raw_bytes[0]
    for i in range(1, len(raw_bytes)):
        encoded[i] = (raw_bytes[i] - raw_bytes[i - 1]) & 0xFF
    return bytes(encoded)


def delta_decode_bytes(delta_bytes: bytes) -> bytes:
    """Inverts first-order byte differences."""
    if not delta_bytes:
        return b""
    decoded = bytearray(len(delta_bytes))
    decoded[0] = delta_bytes[0]
    for i in range(1, len(delta_bytes)):
        decoded[i] = (decoded[i - 1] + delta_bytes[i]) & 0xFF
    return bytes(decoded)


# Compressor implementations
def compress_lz4(data: bytes, level: int = 1) -> bytes:
    if HAS_LZ4 and lz4_frame is not None:
        return lz4_frame.compress(data, compression_level=level)
    return zlib.compress(data, level=1)


def decompress_lz4(data: bytes) -> bytes:
    if HAS_LZ4 and lz4_frame is not None:
        try:
            return lz4_frame.decompress(data)
        except Exception:
            pass
    return zlib.decompress(data)


def compress_zstd(data: bytes, level: int = 3) -> bytes:
    if HAS_ZSTD and zstd is not None:
        cctx = zstd.ZstdCompressor(level=level)
        return cctx.compress(data)
    return zlib.compress(data, level=min(9, max(1, level)))


def decompress_zstd(data: bytes) -> bytes:
    if HAS_ZSTD and zstd is not None:
        try:
            dctx = zstd.ZstdDecompressor()
            return dctx.decompress(data)
        except Exception:
            pass
    return zlib.decompress(data)


def compress_gzip(data: bytes, level: int = 6) -> bytes:
    return zlib.compress(data, level=level)


def decompress_gzip(data: bytes) -> bytes:
    return zlib.decompress(data)


def compress_bzip2(data: bytes, level: int = 9) -> bytes:
    return bz2.compress(data, compresslevel=level)


def decompress_bzip2(data: bytes) -> bytes:
    return bz2.decompress(data)


def compress_snappy(data: bytes, level: int = 1) -> bytes:
    if HAS_SNAPPY and snappy is not None:
        return snappy.compress(data)
    # Fast fallback
    return compress_lz4(data, level=1)


def decompress_snappy(data: bytes) -> bytes:
    if HAS_SNAPPY and snappy is not None:
        try:
            return snappy.decompress(data)
        except Exception:
            pass
    return decompress_lz4(data)


def compress_delta_zlib(data: bytes, level: int = 6) -> bytes:
    return zlib.compress(delta_encode_bytes(data), level=level)


def decompress_delta_zlib(data: bytes) -> bytes:
    return delta_decode_bytes(zlib.decompress(data))


def compress_none(data: bytes, level: int = 0) -> bytes:
    return data


def decompress_none(data: bytes) -> bytes:
    return data


COMPRESSOR_REGISTRY: Dict[str, Dict[str, Any]] = {
    "lz4": {"compress": compress_lz4, "decompress": decompress_lz4, "lossless": True, "default_level": 1},
    "zstd": {"compress": compress_zstd, "decompress": decompress_zstd, "lossless": True, "default_level": 3},
    "zstandard": {"compress": compress_zstd, "decompress": decompress_zstd, "lossless": True, "default_level": 3},
    "gzip": {"compress": compress_gzip, "decompress": decompress_gzip, "lossless": True, "default_level": 6},
    "zlib": {"compress": compress_gzip, "decompress": decompress_gzip, "lossless": True, "default_level": 6},
    "bzip2": {"compress": compress_bzip2, "decompress": decompress_bzip2, "lossless": True, "default_level": 9},
    "bz2": {"compress": compress_bzip2, "decompress": decompress_bzip2, "lossless": True, "default_level": 9},
    "snappy": {"compress": compress_snappy, "decompress": decompress_snappy, "lossless": True, "default_level": 1},
    "delta_zlib": {"compress": compress_delta_zlib, "decompress": decompress_delta_zlib, "lossless": True, "default_level": 6},
    "none": {"compress": compress_none, "decompress": decompress_none, "lossless": True, "default_level": 0},
    "passthrough": {"compress": compress_none, "decompress": decompress_none, "lossless": True, "default_level": 0}
}


def get_compressor(name: str) -> Callable:
    """Retrieves compression function for the given codec name."""
    entry = COMPRESSOR_REGISTRY.get(name.lower(), COMPRESSOR_REGISTRY["none"])
    return entry["compress"]


def get_decompressor(name: str) -> Callable:
    """Retrieves decompression function for the given codec name."""
    entry = COMPRESSOR_REGISTRY.get(name.lower(), COMPRESSOR_REGISTRY["none"])
    return entry["decompress"]


def list_available_codecs() -> List[str]:
    """Returns list of primary available codec names."""
    return ["lz4", "zstd", "gzip", "bzip2", "snappy", "delta_zlib", "none"]


class MemoryBufferPool:
    """
    Zero-copy in-memory buffer pool for high-throughput edge execution.
    Pre-allocates reusable bytearray blocks to prevent heap churn.
    """

    def __init__(self, block_size: int = 65536, pool_capacity: int = 8):
        self.block_size = block_size
        self.pool_capacity = pool_capacity
        self._available_buffers: List[bytearray] = [
            bytearray(self.block_size) for _ in range(pool_capacity)
        ]

    def acquire(self) -> bytearray:
        """Acquires a pre-allocated bytearray buffer."""
        if self._available_buffers:
            return self._available_buffers.pop()
        return bytearray(self.block_size)

    def release(self, buf: bytearray) -> None:
        """Returns buffer to the pool."""
        if len(self._available_buffers) < self.pool_capacity and len(buf) == self.block_size:
            self._available_buffers.append(buf)
