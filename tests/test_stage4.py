"""
Unit Tests for Stage 4: Multi-Objective Decision Engine
"""

import os
import unittest
from edge.stage4_decision import DecisionStage


class TestStage4Decision(unittest.TestCase):

    def setUp(self):
        self.test_log_file = "logs/test_decisions.csv"
        self.stage4 = DecisionStage(log_file=self.test_log_file)

    def tearDown(self):
        if os.path.exists(self.test_log_file):
            try:
                os.remove(self.test_log_file)
            except Exception:
                pass

    def test_strategy_selection_normal_operation(self):
        """Verifies standard decision output structure and fields."""
        features = {"window_id": 10, "entropy": 1.5, "variance": 0.05}
        predictions = {
            "predicted_cpu_temp": 45.0,
            "predicted_cpu_load": 20.0,
            "predicted_bandwidth_kbps": 1000.0,
            "is_throttling_risk": False
        }
        res = self.stage4.select_strategy(features, predictions)

        self.assertEqual(res["window_id"], 10)
        self.assertIn(res["chosen_compressor"], self.stage4.CANDIDATE_CODECS)
        self.assertIn("compression_level", res)
        self.assertEqual(res["transmit_or_defer"], "transmit")
        self.assertIn("composite_score", res)
        self.assertIn("scores_breakdown", res)
        self.assertIn("adapted_weights", res)

    def test_thermal_stress_weight_adaptation(self):
        """Under thermal stress, energy and latency weights are boosted."""
        features = {"window_id": 1, "entropy": 1.5}
        predictions = {
            "predicted_cpu_temp": 75.0,
            "predicted_cpu_load": 95.0,
            "predicted_bandwidth_kbps": 1000.0,
            "is_throttling_risk": True
        }
        res = self.stage4.select_strategy(features, predictions)
        weights = res["adapted_weights"]

        # Energy + Latency should dominate Ratio under thermal stress
        self.assertGreater(weights["w2_energy"] + weights["w3_latency"], weights["w1_ratio"])
        # Selected compressor should be low-energy / fast
        self.assertIn(res["chosen_compressor"], ["lz4", "none", "delta_zlib"])

    def test_bandwidth_depleted_weight_adaptation(self):
        """Under low bandwidth, ratio weight w1 is heavily boosted."""
        features = {"window_id": 2, "entropy": 0.8}
        predictions = {
            "predicted_cpu_temp": 45.0,
            "predicted_cpu_load": 15.0,
            "predicted_bandwidth_kbps": 150.0,
            "is_throttling_risk": False
        }
        res = self.stage4.select_strategy(features, predictions)
        weights = res["adapted_weights"]

        # Ratio weight should dominate
        self.assertGreater(weights["w1_ratio"], weights["w2_energy"])
        self.assertIn(res["chosen_compressor"], ["zstd", "bzip2", "delta_zlib", "gzip"])

    def test_deferral_action_when_bandwidth_is_critical(self):
        """When bandwidth drops below critical threshold (30 kbps), defer transmission."""
        features = {"window_id": 3, "entropy": 1.0}
        predictions = {
            "predicted_cpu_temp": 45.0,
            "predicted_cpu_load": 20.0,
            "predicted_bandwidth_kbps": 15.0,
            "is_throttling_risk": False
        }
        res = self.stage4.select_strategy(features, predictions)
        self.assertEqual(res["transmit_or_defer"], "defer")

    def test_decision_logging_to_csv(self):
        """Verifies that decision context is persisted to CSV."""
        features = {"window_id": 99, "entropy": 1.0, "variance": 0.01}
        predictions = {
            "predicted_cpu_temp": 48.0,
            "predicted_cpu_load": 25.0,
            "predicted_bandwidth_kbps": 800.0,
            "is_throttling_risk": False
        }
        self.stage4.select_strategy(features, predictions)

        self.assertTrue(os.path.exists(self.test_log_file))
        with open(self.test_log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            self.assertGreaterEqual(len(lines), 2)  # Header + 1 record
            self.assertIn("99", lines[1])


if __name__ == "__main__":
    unittest.main()

