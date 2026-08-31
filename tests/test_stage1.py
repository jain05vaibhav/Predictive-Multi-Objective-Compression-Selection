"""
Unit Tests for Stage 1: Data Acquisition & Windowing (Raspberry Pi 3B+)
"""

import unittest
import time
from edge.stage1_acquisition import AcquisitionStage, Window
from edge.sensors.telemetry_source import RPiTelemetryHub


class TestStage1Acquisition(unittest.TestCase):

    def test_window_object_properties(self):
        """Test Window dataclass methods, dict conversion, and byte serialization."""
        raw_samples = [{"temperature": 24.5, "humidity": 55.0, "cpu_temp_c": 42.0} for _ in range(10)]
        win = Window(window_id=42, data=raw_samples, data_type="numeric", timestamp=1000.0)

        self.assertEqual(win.window_id, 42)
        self.assertEqual(win.sample_count, 10)
        self.assertEqual(win.data_type, "numeric")
        self.assertEqual(win.timestamp, 1000.0)

        # Dictionary representation
        d = win.to_dict()
        self.assertEqual(d["window_id"], 42)
        self.assertEqual(d["sample_count"], 10)
        self.assertEqual(len(d["data"]), 10)

        # Raw byte serialization
        raw_bytes = win.to_bytes()
        self.assertIsInstance(raw_bytes, bytes)
        self.assertGreater(len(raw_bytes), 0)

        # Dict-like item access
        self.assertEqual(win["window_id"], 42)
        self.assertEqual(win["sample_count"], 10)

    def test_acquire_100_telemetry_readings_partitions_into_100_over_n_windows(self):
        """
        Roadmap Verification: Feed 100 readings, assert you get 100/N
        windows each of size N.
        """
        n = 25
        total_samples = 100
        source = RPiTelemetryHub()
        stage = AcquisitionStage(source=source, window_size=n)

        # Collect 100 samples in total via 4 sequential windows
        windows = []
        for _ in range(total_samples // n):
            w = stage.acquire_window(window_size=n)
            windows.append(w)

        self.assertEqual(len(windows), 4)  # 100 / 25 = 4 windows
        for i, w in enumerate(windows, start=1):
            self.assertEqual(w.window_id, i)
            self.assertEqual(w.sample_count, n)
            self.assertEqual(len(w.data), n)

    def test_acquire_window_with_custom_list_source(self):
        """Test feeding a finite synthetic list of 100 items."""
        sample_pool = [i for i in range(100)]
        stage = AcquisitionStage(source=sample_pool, window_size=20)

        windows = []
        while len(sample_pool) > 0:
            w = stage.acquire_window(source=sample_pool, window_size=20)
            windows.append(w)

        self.assertEqual(len(windows), 5)  # 100 / 20 = 5
        for w in windows:
            self.assertEqual(w.sample_count, 20)

    def test_acquire_window_timeout(self):
        """Verify that acquisition honors timeout T_max if source produces slowly."""
        def slow_source():
            time.sleep(0.05)
            return {"val": 1}

        stage = AcquisitionStage(source=slow_source, window_size=50, max_wait_time=0.15)
        start = time.time()
        w = stage.acquire_window(window_size=50, timeout=0.15)
        elapsed = time.time() - start

        # Should finish around 0.15s with fewer than 50 samples
        self.assertLess(elapsed, 0.40)
        self.assertLess(w.sample_count, 50)
        self.assertGreater(w.sample_count, 0)

    def test_stream_windows_generator(self):
        """Test stream_windows generator produces correct number of windows."""
        stage = AcquisitionStage(window_size=5)
        stream = list(stage.stream_windows(max_windows=3, sample_interval=0.0))
        self.assertEqual(len(stream), 3)
        for w in stream:
            self.assertEqual(w.sample_count, 5)


if __name__ == "__main__":
    unittest.main()
