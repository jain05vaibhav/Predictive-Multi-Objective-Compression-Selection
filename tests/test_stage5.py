"""
Unit Tests for Stage 5: Dynamic Compression Execution Engine
"""

import unittest
from edge.stage5_compression import (
    CompressionStage,
    delta_encode_bytes,
    delta_decode_bytes
)
from edge.stage1_acquisition import Window


class TestStage5Compression(unittest.TestCase):

    def setUp(self):
        self.stage5 = CompressionStage()
        self.sample_telemetry = [
            {
                "timestamp": 1788200000.0 + i * 0.1,
                "temperature": 23.5 + (i * 0.01),
                "humidity": 60.0,
                "cpu_temp_c": 38.5,
                "cpu_percent": 15.0,
                "core_voltage_v": 1.25
            }
            for i in range(50)
        ]

    def test_all_codecs_lossless_reconstruction(self):
        """Verify that every supported codec can compress and decompress losslessly."""
        test_payload = b"SENSOR_DATA_STREAM_TEST_PACKET_LOSSLESS_VERIFICATION_12345"
        for codec in self.stage5.AVAILABLE_CODECS:
            with self.subTest(codec=codec):
                is_lossless = self.stage5.verify_lossless(test_payload, codec=codec)
                self.assertTrue(is_lossless, f"Codec {codec} failed lossless reconstruction")

    def test_compression_ratio_greater_than_one_on_redundant_data(self):
        """Repetitive telemetry payload should compress to a ratio > 1.0 for active codecs."""
        for codec in ["lz4", "zstd", "bzip2", "gzip", "delta_zlib"]:
            res = self.stage5.compress(self.sample_telemetry, codec=codec)
            self.assertGreater(res["compression_ratio"], 1.0, f"Codec {codec} failed to achieve compression")
            self.assertGreater(res["space_savings_percent"], 0.0)
            self.assertGreater(res["raw_size_bytes"], res["compressed_size_bytes"])

    def test_passthrough_codec_behavior(self):
        """Passthrough ('none') should return exact bytes and ratio == 1.0."""
        raw_bytes = b"RAW_UNCOMPRESSED_PAYLOAD"
        res = self.stage5.compress(raw_bytes, codec="none")
        self.assertEqual(res["compressed_size_bytes"], len(raw_bytes))
        self.assertEqual(res["compression_ratio"], 1.0)
        self.assertEqual(res["space_savings_percent"], 0.0)
        self.assertEqual(res["compressed_payload"], raw_bytes)

    def test_delta_byte_encoding_and_inversion(self):
        """Verify byte-level delta difference encoding and reverse decoding."""
        original = bytes([10, 12, 15, 15, 20, 25, 30, 28, 25, 100, 200, 255])
        delta = delta_encode_bytes(original)
        reconstructed = delta_decode_bytes(delta)
        self.assertEqual(original, reconstructed)

    def test_window_object_direct_input_support(self):
        """Verify passing a Stage 1 Window instance directly into compress()."""
        win = Window(window_id=42, data=self.sample_telemetry, data_type="numeric")
        res = self.stage5.compress(win, codec="gzip")
        self.assertEqual(res["window_id"], 0)  # default if not explicitly overridden
        self.assertGreater(res["compression_ratio"], 1.0)

        decompressed = self.stage5.decompress(res["compressed_payload"], codec="gzip")
        self.assertEqual(win.to_bytes(), decompressed)

    def test_compress_payload_adapter(self):
        """Verify the compress_payload pipeline adapter using both tuple and dict decision formats."""
        win = Window(window_id=7, data=self.sample_telemetry, data_type="numeric")

        # 1. Tuple decision format: ("zstd", 3)
        res_tuple = self.stage5.compress_payload(win, ("zstd", 3))
        self.assertEqual(res_tuple["window_id"], 7)
        self.assertEqual(res_tuple["compressor_used"], "zstd")

        # 2. Dict decision format
        decision_dict = {
            "window_id": 7,
            "chosen_compressor": "bzip2",
            "compression_level": 2
        }
        res_dict = self.stage5.compress_payload(win, decision_dict)
        self.assertEqual(res_dict["window_id"], 7)
        self.assertEqual(res_dict["compressor_used"], "bzip2")

    def test_benchmark_all_codecs_returns_full_matrix(self):
        """benchmark_all_codecs must return a complete report for all candidate codecs."""
        bench = self.stage5.benchmark_all_codecs(self.sample_telemetry)
        for codec in self.stage5.AVAILABLE_CODECS:
            self.assertIn(codec, bench)
            self.assertTrue(bench[codec]["lossless"])
            self.assertGreater(bench[codec]["latency_ms"], 0.0)


if __name__ == "__main__":
    unittest.main()

