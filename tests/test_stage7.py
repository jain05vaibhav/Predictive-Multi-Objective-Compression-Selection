"""
Unit Tests for Stage 7: Cloud Receiver & Outcome Store
"""

import os
import unittest
from cloud.receiver import CloudReceiver
from cloud.outcome_store import OutcomeStore
from edge.stage5_compression import CompressionStage


class TestStage7CloudReceiver(unittest.TestCase):

    def setUp(self):
        self.test_log_file = "logs/test_cloud_outcomes.csv"
        self.receiver = CloudReceiver(log_file=self.test_log_file)
        self.comp = CompressionStage()

    def tearDown(self):
        if os.path.exists(self.test_log_file):
            try:
                os.remove(self.test_log_file)
            except Exception:
                pass

    def test_cloud_ingestion_and_lossless_decompression(self):
        """Cloud receiver must ingest compressed packet, decompress it, and report 0.0 error."""
        raw_data = [{"temperature": 24.0 + i, "humidity": 55.0} for i in range(10)]
        comp_res = self.comp.compress(raw_data, codec="zstd")

        packet = {
            "window_id": 101,
            "compressor": comp_res["compressor_used"],
            "compression_level": comp_res["compression_level"],
            "raw_size_bytes": comp_res["raw_size_bytes"],
            "compressed_size_bytes": comp_res["compressed_size_bytes"],
            "execution_time_ms": comp_res["execution_time_ms"],
            "cpu_energy_proxy_uj": comp_res["cpu_energy_proxy_uj"],
            "payload_bytes": comp_res["compressed_payload"],
            "transfer_time_ms": 3.5
        }

        res = self.receiver.receive_and_process_payload(packet)
        self.assertEqual(res["window_id"], 101)
        self.assertEqual(res["reconstruction_error"], 0.0)
        self.assertEqual(res["status"], "verified")
        self.assertGreater(res["decompressed_bytes_count"], 0)

    def test_outcome_logging_to_csv(self):
        """Ingesting packet commits record to CSV log file."""
        comp_res = self.comp.compress([{"temperature": 25.0}], codec="lz4")
        packet = {
            "window_id": 1,
            "compressor": "lz4",
            "compression_level": 1,
            "raw_size_bytes": comp_res["raw_size_bytes"],
            "compressed_size_bytes": comp_res["compressed_size_bytes"],
            "execution_time_ms": comp_res["execution_time_ms"],
            "cpu_energy_proxy_uj": comp_res["cpu_energy_proxy_uj"],
            "payload_bytes": comp_res["compressed_payload"],
            "transfer_time_ms": 2.1
        }
        self.receiver.receive_and_process_payload(packet)


        self.assertTrue(os.path.exists(self.test_log_file))
        records = self.receiver.outcome_store.get_recent_outcomes(n=10)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["window_id"], "1")
        self.assertEqual(records[0]["compressor"], "lz4")

    def test_outcome_store_statistical_aggregation(self):
        """Summary stats compute correct totals and percentage savings."""
        store = OutcomeStore(log_file=self.test_log_file)
        store.record_outcome({
            "window_id": 1, "compressor": "lz4", "raw_bytes": 1000,
            "compressed_bytes": 250, "ratio": 4.0, "latency_ms": 1.0,
            "energy_uj": 2000.0, "error": 0.0, "transfer_time_ms": 2.0
        })
        store.record_outcome({
            "window_id": 2, "compressor": "zstd", "raw_bytes": 1000,
            "compressed_bytes": 100, "ratio": 10.0, "latency_ms": 2.0,
            "energy_uj": 4000.0, "error": 0.0, "transfer_time_ms": 3.0
        })

        stats = store.get_summary_stats()
        self.assertEqual(stats["total_windows"], 2)
        self.assertEqual(stats["total_raw_bytes"], 2000)
        self.assertEqual(stats["total_compressed_bytes"], 350)
        self.assertEqual(stats["overall_bandwidth_saved_pct"], 82.5)
        self.assertEqual(stats["average_compression_ratio"], 7.0)

    def test_reconstruction_error_calculation(self):
        """Error function returns 0.0 for identical bytes and > 0.0 for mismatched bytes."""
        orig = b"DATA_STREAM_TEST"
        self.assertEqual(self.receiver.calculate_reconstruction_error(orig, orig), 0.0)

        modified = b"DATA_STREAM_DIFF"
        self.assertGreater(self.receiver.calculate_reconstruction_error(orig, modified), 0.0)


if __name__ == "__main__":
    unittest.main()

