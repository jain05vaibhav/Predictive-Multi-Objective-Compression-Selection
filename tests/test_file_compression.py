"""
Unit Tests for AURA-EDGE Multi-Objective File Compression Engine
"""

import unittest
import os
import json
from edge.file_compression import FileCompressionEngine


class TestFileCompressionEngine(unittest.TestCase):

    def setUp(self):
        self.engine = FileCompressionEngine()

    def test_analyze_empty_file(self):
        analysis = self.engine.analyze_file(b"", "empty.bin")
        self.assertEqual(analysis["raw_size_bytes"], 0)
        self.assertEqual(analysis["entropy"], 0.0)

    def test_analyze_repetitive_file(self):
        # Repetitive bytes have low Shannon entropy
        data = b"AAAAAAAAAAAAAAAA" * 100
        analysis = self.engine.analyze_file(data, "test.txt")
        self.assertEqual(analysis["raw_size_bytes"], 1600)
        self.assertEqual(analysis["entropy"], 0.0)
        self.assertEqual(analysis["unique_bytes"], 1)

    def test_analyze_structured_telemetry_csv(self):
        csv_data = b"timestamp,temp,volts\n1.0,24.5,1.25\n2.0,24.6,1.25\n" * 50
        analysis = self.engine.analyze_file(csv_data, "telemetry.csv")
        self.assertEqual(analysis["modality"], "numeric")
        self.assertGreater(analysis["entropy"], 0.0)

    def test_compress_file_lossless_exact_match(self):
        original = b"AURA-EDGE-HIGH-PERFORMANCE-TEST-PAYLOAD-1234567890-" * 20
        res = self.engine.compress_file(original, codec="zstd", benchmark_all=True)

        self.assertTrue(res["is_lossless"])
        self.assertEqual(res["reconstruction_error"], 0.0)
        self.assertGreater(res["compression_ratio"], 1.0)
        self.assertGreater(res["saved_bytes"], 0)
        self.assertEqual(len(res["benchmark"]), 6)

        # Verify all candidates in benchmark
        candidate_codecs = [b["codec"] for b in res["benchmark"]]
        for cand in ["lz4", "zstd", "delta_zlib", "gzip", "bzip2", "none"]:
            self.assertIn(cand, candidate_codecs)

    def test_recommend_codec_adapts_under_resource_pressure(self):
        features = {"entropy": 1.5, "variance": 0.2, "modality": "numeric"}
        
        # Under normal conditions
        normal_ctx = {"predicted_bandwidth_kbps": 1200.0, "is_throttling_risk": False}
        rec_normal = self.engine.recommend_codec(features, normal_ctx)
        self.assertIn("chosen_compressor", rec_normal)

        # Under extreme bandwidth pinching (<30 kbps)
        pinched_ctx = {"predicted_bandwidth_kbps": 20.0, "is_throttling_risk": False}
        rec_pinched = self.engine.recommend_codec(features, pinched_ctx)
        self.assertIn("chosen_compressor", rec_pinched)


if __name__ == "__main__":
    unittest.main()
