"""
Unit Tests for Stage 2: Feature Extraction (Raspberry Pi 3B+)
"""

import unittest
import math
import numpy as np
from edge.stage1_acquisition import Window
from edge.stage2_features import FeatureExtractionStage


class TestStage2Features(unittest.TestCase):

    def setUp(self):
        self.extractor = FeatureExtractionStage(num_bins=16)

    def test_constant_value_window_entropy_near_zero(self):
        """
        Roadmap Verification: Feed a constant-value window -> expect entropy ≈ 0.
        Also variance = 0.0, rate_of_change = 0.0.
        """
        const_data = [24.5] * 50
        win = Window(window_id=1, data=const_data, data_type="numeric")
        features = self.extractor.extract_features(win)

        self.assertAlmostEqual(features["entropy"], 0.0, places=4)
        self.assertAlmostEqual(features["variance"], 0.0, places=4)
        self.assertAlmostEqual(features["rate_of_change"], 0.0, places=4)
        self.assertEqual(features["sample_count"], 50)
        self.assertEqual(features["data_type"], "numeric")

    def test_uniform_random_noise_entropy_approaches_log2_bins(self):
        """
        Roadmap Verification: Feed uniform random noise -> expect entropy near log2(num_buckets).
        For num_bins=16, theoretical max entropy is log2(16) = 4.0.
        """
        np.random.seed(42)
        # Uniform spread across [0, 100] with 5000 samples to fill all 16 bins equally
        uniform_data = list(np.random.uniform(0.0, 100.0, size=5000))
        win = Window(window_id=2, data=uniform_data, data_type="numeric")
        features = self.extractor.extract_features(win)

        theoretical_max = math.log2(16)  # 4.0
        # With 5000 uniform samples, entropy should be very close to 4.0 (e.g. > 3.95)
        self.assertGreater(features["entropy"], 3.95)
        self.assertLessEqual(features["entropy"], theoretical_max + 1e-4)

    def test_hand_calculated_variance_and_rate_of_change(self):
        """
        Roadmap Verification: Entropy/variance/rate-of-change outputs match
        hand-calculated values on small hardcoded examples.
        
        Example 1: [10.0, 20.0, 30.0, 40.0, 50.0]
        Mean = 30.0
        Variance (ddof=0) = ((10-30)^2 + (20-30)^2 + (30-30)^2 + (40-30)^2 + (50-30)^2) / 5
                          = (400 + 100 + 0 + 100 + 400) / 5 = 1000 / 5 = 200.0
        Step differences = [10, 10, 10, 10]
        Rate of change = mean([10, 10, 10, 10]) = 10.0
        """
        hardcoded_data = [10.0, 20.0, 30.0, 40.0, 50.0]
        win = {"window_id": 3, "data": hardcoded_data, "data_type": "numeric"}
        features = self.extractor.extract_features(win)

        self.assertEqual(features["sample_count"], 5)
        self.assertAlmostEqual(features["variance"], 200.0, places=3)
        self.assertAlmostEqual(features["rate_of_change"], 10.0, places=3)
        self.assertAlmostEqual(features["min_val"], 10.0, places=3)
        self.assertAlmostEqual(features["max_val"], 50.0, places=3)
        self.assertAlmostEqual(features["mean_val"], 30.0, places=3)

    def test_dict_sensor_samples_extraction(self):
        """Test feature extraction from telemetry dicts containing sensor keys."""
        sensor_data = [
            {"temperature": 20.0 + i * 0.5, "humidity": 50.0 - i, "cpu_temp_c": 42.0 + i * 0.2}
            for i in range(10)
        ]
        win = Window(window_id=4, data=sensor_data, data_type="numeric")
        
        # By default extracts 'temperature'
        features = self.extractor.extract_features(win)
        self.assertEqual(features["sample_count"], 10)
        self.assertAlmostEqual(features["rate_of_change"], 0.5, places=3)
        self.assertAlmostEqual(features["min_val"], 20.0, places=3)
        self.assertAlmostEqual(features["max_val"], 24.5, places=3)

        # Explicitly extract 'humidity'
        hum_features = self.extractor.extract_features(win, feature_key="humidity")
        self.assertAlmostEqual(hum_features["rate_of_change"], 1.0, places=3)
        self.assertAlmostEqual(hum_features["min_val"], 41.0, places=3)
        self.assertAlmostEqual(hum_features["max_val"], 50.0, places=3)

        # Explicitly extract 'cpu_temp_c'
        cpu_features = self.extractor.extract_features(win, feature_key="cpu_temp_c")
        self.assertAlmostEqual(cpu_features["rate_of_change"], 0.2, places=3)
        self.assertAlmostEqual(cpu_features["min_val"], 42.0, places=3)
        self.assertAlmostEqual(cpu_features["max_val"], 43.8, places=3)

    def test_edge_cases_empty_and_single_sample(self):
        """Test graceful degradation with empty or single sample data."""
        # Empty
        empty_features = self.extractor.extract_features({"data": []})
        self.assertEqual(empty_features["sample_count"], 0)
        self.assertEqual(empty_features["entropy"], 0.0)
        self.assertEqual(empty_features["variance"], 0.0)
        self.assertEqual(empty_features["rate_of_change"], 0.0)

        # Single sample
        single_features = self.extractor.extract_features({"data": [42.0]})
        self.assertEqual(single_features["sample_count"], 1)
        self.assertEqual(single_features["entropy"], 0.0)
        self.assertEqual(single_features["variance"], 0.0)
        self.assertEqual(single_features["rate_of_change"], 0.0)


if __name__ == "__main__":
    unittest.main()
