"""
Unit Tests for Raspberry Pi 3B+ Native System Telemetry Reader
"""

import unittest
from edge.sensors.rpi_system_reader import RPiSystemReader


class TestRPiSystemReader(unittest.TestCase):

    def setUp(self):
        self.reader = RPiSystemReader()

    def test_parse_temp_output(self):
        """Test parsing of vcgencmd measure_temp output."""
        self.assertEqual(RPiSystemReader.parse_temp_output("temp=42.8'C"), 42.8)
        self.assertEqual(RPiSystemReader.parse_temp_output("temp=58.2'C\n"), 58.2)
        self.assertEqual(RPiSystemReader.parse_temp_output("temp=35.0'C"), 35.0)
        self.assertIsNone(RPiSystemReader.parse_temp_output("invalid output"))
        self.assertIsNone(RPiSystemReader.parse_temp_output(""))

    def test_parse_clock_output(self):
        """Test parsing of vcgencmd measure_clock arm/core outputs."""
        # 1.4 GHz ARM clock -> 1400.0 MHz
        self.assertEqual(RPiSystemReader.parse_clock_output("frequency(45)=1400000000"), 1400.0)
        # 400 MHz Core clock -> 400.0 MHz
        self.assertEqual(RPiSystemReader.parse_clock_output("frequency(1)=400000000"), 400.0)
        # 600 MHz Idle ARM clock -> 600.0 MHz
        self.assertEqual(RPiSystemReader.parse_clock_output("frequency(45)=600000000\n"), 600.0)
        self.assertIsNone(RPiSystemReader.parse_clock_output("error"))

    def test_parse_volts_output(self):
        """Test parsing of vcgencmd measure_volts outputs."""
        self.assertEqual(RPiSystemReader.parse_volts_output("volt=1.2000V"), 1.2)
        self.assertEqual(RPiSystemReader.parse_volts_output("volt=1.2500V\n"), 1.25)
        self.assertEqual(RPiSystemReader.parse_volts_output("volt=1.3500V"), 1.35)
        self.assertIsNone(RPiSystemReader.parse_volts_output("invalid"))

    def test_parse_throttled_output_normal(self):
        """Test throttled=0x0 indicates no throttling and normal voltage."""
        res = RPiSystemReader.parse_throttled_output("throttled=0x0")
        self.assertEqual(res["throttled_hex"], "0x0")
        self.assertEqual(res["throttled_raw"], 0)
        self.assertFalse(res["undervoltage_now"])
        self.assertFalse(res["arm_freq_capped_now"])
        self.assertFalse(res["throttled_now"])
        self.assertFalse(res["soft_temp_limit_now"])
        self.assertFalse(res["undervoltage_occurred"])
        self.assertFalse(res["throttling_occurred"])

    def test_parse_throttled_output_active_undervoltage_and_throttling(self):
        """Test bitmask parsing when undervoltage and throttling are detected."""
        # 0x50005: bits 0 (undervoltage now), 2 (throttled now), 16 (undervoltage occurred), 18 (throttled occurred)
        res = RPiSystemReader.parse_throttled_output("throttled=0x50005")
        self.assertEqual(res["throttled_hex"], "0x50005")
        self.assertTrue(res["undervoltage_now"])
        self.assertFalse(res["arm_freq_capped_now"])
        self.assertTrue(res["throttled_now"])
        self.assertTrue(res["undervoltage_occurred"])
        self.assertTrue(res["throttling_occurred"])

    def test_parse_throttled_output_arm_freq_capped(self):
        """Test bitmask parsing when ARM frequency capping occurred."""
        # 0x20002: bits 1 (arm freq capped now), 17 (arm freq capped occurred)
        res = RPiSystemReader.parse_throttled_output("throttled=0x20002")
        self.assertTrue(res["arm_freq_capped_now"])
        self.assertTrue(res["arm_freq_capped_occurred"])
        self.assertFalse(res["undervoltage_now"])

    def test_cpu_metrics_via_psutil(self):
        """Verify CPU utilization and core count metrics."""
        cpu_metrics = self.reader.read_cpu_metrics()
        self.assertIn("cpu_percent", cpu_metrics)
        self.assertIn("cpu_count", cpu_metrics)
        self.assertIn("load_1m", cpu_metrics)
        self.assertGreaterEqual(cpu_metrics["cpu_count"], 1)
        self.assertGreaterEqual(cpu_metrics["cpu_percent"], 0.0)
        self.assertLessEqual(cpu_metrics["cpu_percent"], 100.0)

    def test_memory_metrics_via_psutil(self):
        """Verify memory statistics."""
        mem_metrics = self.reader.read_memory_metrics()
        self.assertIn("memory_total_mb", mem_metrics)
        self.assertIn("memory_used_mb", mem_metrics)
        self.assertIn("memory_percent", mem_metrics)
        self.assertGreater(mem_metrics["memory_total_mb"], 0.0)
        self.assertGreaterEqual(mem_metrics["memory_percent"], 0.0)
        self.assertLessEqual(mem_metrics["memory_percent"], 100.0)

    def test_read_all_system_metrics_structure(self):
        """Verify read_all_system_metrics returns all required hardware fields."""
        metrics = self.reader.read_all_system_metrics()
        required_keys = [
            "cpu_temp_c", "cpu_freq_mhz", "core_freq_mhz", "core_voltage_v",
            "sdram_c_voltage_v", "sdram_i_voltage_v", "sdram_p_voltage_v",
            "throttled_hex", "undervoltage_now", "throttled_now",
            "cpu_percent", "cpu_count", "load_1m", "memory_total_mb", "memory_percent"
        ]
        for k in required_keys:
            self.assertIn(k, metrics)


if __name__ == "__main__":
    unittest.main()
