"""
Unit Tests for Shared Compressor Registry & Memory Buffer Pool
"""

import unittest
from shared.compressors import (
    get_compressor,
    get_decompressor,
    list_available_codecs,
    MemoryBufferPool
)


class TestSharedCompressors(unittest.TestCase):

    def setUp(self):
        self.sample_payload = b"TEMPERATUREREADING_1234567890_" * 20

    def test_all_codecs_roundtrip_lossless(self):
        """All registered codecs successfully compress and invert losslessly."""
        codecs = list_available_codecs()
        for c in codecs:
            compress_fn = get_compressor(c)
            decompress_fn = get_decompressor(c)

            compressed = compress_fn(self.sample_payload)
            self.assertIsInstance(compressed, bytes)
            decompressed = decompress_fn(compressed)
            self.assertEqual(decompressed, self.sample_payload, f"Codec {c} failed roundtrip")

    def test_memory_buffer_pool(self):
        """Memory buffer pool acquires and releases pre-allocated buffers without leaks."""
        pool = MemoryBufferPool(block_size=1024, pool_capacity=4)
        buf1 = pool.acquire()
        buf2 = pool.acquire()

        self.assertEqual(len(buf1), 1024)
        self.assertEqual(len(buf2), 1024)

        pool.release(buf1)
        pool.release(buf2)
        buf3 = pool.acquire()
        self.assertEqual(len(buf3), 1024)


if __name__ == "__main__":
    unittest.main()
