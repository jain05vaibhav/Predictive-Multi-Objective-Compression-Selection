"""
Unit Tests for Stage 1 Dynamic Window Modulation & Multi-Modal Acquisition
"""

import unittest
from edge.stage1_acquisition import AcquisitionStage, Window
from edge.sensors.text_log_reader import TextLogReader


class TestStage1MultiModal(unittest.TestCase):

    def test_dynamic_window_modulation(self):
        """Window size adapts based on rate of change and entropy."""
        stage1 = AcquisitionStage(window_size=20)
        self.assertEqual(stage1.window_size, 20)

        # Steady state -> expands
        expanded = stage1.adjust_window_size(rate_of_change=0.01, entropy=0.5)
        self.assertGreater(expanded, 20)

        # High volatility -> contracts
        contracted = stage1.adjust_window_size(rate_of_change=1.2, entropy=3.5)
        self.assertLess(contracted, 20)
        self.assertGreaterEqual(contracted, 2)

    def test_text_log_acquisition(self):
        """Acquires text log window and serializes to bytes properly."""
        log_reader = TextLogReader()
        stage1 = AcquisitionStage(source=log_reader, window_size=5, data_type="text")
        window = stage1.acquire_window()

        self.assertEqual(window.sample_count, 5)
        self.assertEqual(window.data_type, "text")
        raw_bytes = window.to_bytes()
        self.assertIsInstance(raw_bytes, bytes)
        self.assertGreater(len(raw_bytes), 0)


if __name__ == "__main__":
    unittest.main()
