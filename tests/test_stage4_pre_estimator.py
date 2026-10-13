"""
Unit Tests for Stage 4 Pre-Execution Cost Estimator
"""

import unittest
from edge.stage4_pre_estimator import PreExecutionCostEstimator


class TestStage4PreEstimator(unittest.TestCase):

    def setUp(self):
        self.estimator = PreExecutionCostEstimator(learning_rate=0.1)

    def test_pre_execution_estimation_monotonic_with_entropy(self):
        """Higher entropy predicts lower compression ratio across algorithms."""
        low_h_features = {"entropy": 0.2, "variance": 0.01, "data_type": "numeric"}
        high_h_features = {"entropy": 3.8, "variance": 1.5, "data_type": "numeric"}

        est_low = self.estimator.estimate_candidate("lz4", low_h_features, raw_size_bytes=4096)
        est_high = self.estimator.estimate_candidate("lz4", high_h_features, raw_size_bytes=4096)

        self.assertGreater(est_low["estimated_ratio"], est_high["estimated_ratio"])
        self.assertGreater(est_low["estimated_ratio"], 1.0)
        self.assertGreater(est_low["estimated_latency_ms"], 0.0)
        self.assertGreater(est_low["estimated_energy_uj"], 0.0)

    def test_estimate_all_candidates_covers_candidates(self):
        """estimate_all_candidates returns predictions for all registered candidate codecs."""
        features = {"entropy": 1.2, "variance": 0.1}
        estimates = self.estimator.estimate_all_candidates(features, raw_size_bytes=2048)

        for c in ["lz4", "zstd", "bzip2", "gzip", "delta_zlib", "none"]:
            self.assertIn(c, estimates)
            self.assertIn("estimated_ratio", estimates[c])
            self.assertIn("estimated_latency_ms", estimates[c])

    def test_online_model_update(self):
        """Measured outcome refines model parameters over time."""
        features = {"entropy": 1.0}
        initial_ratio = self.estimator.models["lz4"]["base_ratio"]

        # Feed an outcome showing better-than-expected ratio
        res = self.estimator.update_model(
            "lz4",
            features,
            {"ratio": 8.0, "latency_ms": 0.05, "raw_bytes": 1024}
        )

        self.assertEqual(res["codec"], "lz4")
        self.assertGreater(res["updated_base_ratio"], initial_ratio)


if __name__ == "__main__":
    unittest.main()
