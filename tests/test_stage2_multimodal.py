"""
Unit Tests for Stage 2 Multi-Modal Feature Extraction (Text & Image)
"""

import unittest
from edge.stage2_features import FeatureExtractionStage


class TestStage2MultiModal(unittest.TestCase):

    def setUp(self):
        self.extractor = FeatureExtractionStage()

    def test_image_feature_extraction(self):
        """Extracts 2D entropy and spatial gradient variance from simulated image bytes."""
        # Simulated pixel buffer (grayscale gradient)
        dummy_pixels = bytes([i % 256 for i in range(1024)])
        win = {
            "window_id": 1,
            "data_type": "image",
            "data": [{"image_bytes": dummy_pixels}]
        }
        feats = self.extractor.extract_features(win)

        self.assertEqual(feats["data_type"], "image")
        self.assertIn("entropy", feats)
        self.assertIn("spatial_gradient_variance", feats)
        self.assertGreater(feats["entropy"], 0.0)

    def test_text_feature_extraction(self):
        """Extracts byte entropy, repetition index, and ASCII ratio from text logs."""
        sample_logs = [
            {"raw_text": "2026-10-13 [INFO] sensor_hub: reading successful seq=1\n"},
            {"raw_text": "2026-10-13 [INFO] sensor_hub: reading successful seq=2\n"},
            {"raw_text": "2026-10-13 [INFO] sensor_hub: reading successful seq=3\n"}
        ]
        win = {
            "window_id": 2,
            "data_type": "text",
            "data": sample_logs
        }
        feats = self.extractor.extract_features(win)

        self.assertEqual(feats["data_type"], "text")
        self.assertIn("entropy", feats)
        self.assertIn("repetition_index", feats)
        self.assertIn("ascii_ratio", feats)
        self.assertGreater(feats["ascii_ratio"], 0.9)
        self.assertGreater(feats["repetition_index"], 0.0)


if __name__ == "__main__":
    unittest.main()
