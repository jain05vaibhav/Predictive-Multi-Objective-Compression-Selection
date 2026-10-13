"""
Unit Tests for Stage 4: Self-Calibrating Hardware Profiler (Objective O4) & Section 2.12 Overhead
"""

import os
import unittest
from edge.stage4_profiler import HardwareProfilerStage


class TestStage4Profiler(unittest.TestCase):

    def setUp(self):
        self.test_log_file = "logs/test_profiler_overhead.csv"
        self.profiler = HardwareProfilerStage(beta=0.15, overhead_log_file=self.test_log_file)

    def tearDown(self):
        if os.path.exists(self.test_log_file):
            try:
                os.remove(self.test_log_file)
            except Exception:
                pass

    def test_profiler_initialization_and_candidate_coverage(self):
        """Verifies that profiler initializes calibration table for all candidates and context buckets."""
        table = self.profiler.get_calibration_table()
        self.assertIn("numeric_low", table)
        self.assertIn("numeric_med", table)
        self.assertIn("numeric_high", table)
        for codec in self.profiler.CANDIDATE_CODECS:
            self.assertIn(codec, table["numeric_med"])
            entry = table["numeric_med"][codec]
            self.assertIn("ratio", entry)
            self.assertIn("latency_ms_per_kb", entry)
            self.assertIn("energy_uj_per_kb", entry)
            self.assertIn("error", entry)

    def test_context_bucket_categorization(self):
        """Tests entropy and data type context classification."""
        self.assertEqual(self.profiler.get_context_bucket({"data_type": "numeric", "entropy": 0.4}), "numeric_low")
        self.assertEqual(self.profiler.get_context_bucket({"data_type": "numeric", "entropy": 1.6}), "numeric_med")
        self.assertEqual(self.profiler.get_context_bucket({"data_type": "numeric", "entropy": 3.2}), "numeric_high")
        self.assertEqual(self.profiler.get_context_bucket({"data_type": "image", "entropy": 2.0}), "image_med")
        self.assertEqual(self.profiler.get_context_bucket({"data_type": "text", "entropy": 2.0}), "text_med")

    def test_moving_average_calibration_update(self):
        """
        Roadmap Verification: Test calibration update formula:
          C_bar_k <- C_bar_k + beta * (C_meas - C_bar_k)
        """
        context = {"data_type": "numeric", "entropy": 1.5}
        initial_profile = self.profiler.get_calibrated_profile("lz4", context)
        init_ratio = initial_profile["ratio"]

        # Measured real ratio 8.0 on 2048-byte payload
        measured = {
            "raw_size_bytes": 2048,
            "ratio": 8.0,
            "latency_ms": 0.20,
            "energy_uj": 120.0,
            "error": 0.0
        }
        updated = self.profiler.update_calibration("lz4", measured, context)

        expected_ratio = round(init_ratio + 0.15 * (8.0 - init_ratio), 4)
        self.assertAlmostEqual(updated["ratio"], expected_ratio, places=3)
        self.assertEqual(updated["updates_count"], 1)

    def test_controller_overhead_recording(self):
        """Verifies Section 2.12 controller overhead metrics (CPU time, RAM, worst decision latency)."""
        self.profiler.start_controller_window()
        report = self.profiler.record_controller_overhead(window_id=42, decision_latency_ms=0.65)

        self.assertEqual(report["window_id"], 42)
        self.assertGreaterEqual(report["controller_ram_mb"], 0.0)
        self.assertEqual(report["decision_latency_ms"], 0.65)
        self.assertEqual(report["worst_case_decision_latency_ms"], 0.65)

        # Record higher latency and verify worst-case tracking
        second_report = self.profiler.record_controller_overhead(window_id=43, decision_latency_ms=1.45)
        self.assertEqual(second_report["worst_case_decision_latency_ms"], 1.45)

        self.assertTrue(os.path.exists(self.test_log_file))


if __name__ == "__main__":
    unittest.main()
