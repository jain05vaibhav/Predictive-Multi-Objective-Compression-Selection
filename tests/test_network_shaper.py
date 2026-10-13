"""
Unit Tests for Traffic Shaper & Network Variability Emulation
"""

import unittest
from network_sim.traffic_shaper import TrafficShaper


class TestTrafficShaper(unittest.TestCase):

    def setUp(self):
        self.shaper = TrafficShaper(interface="lo")

    def test_available_profiles(self):
        """Verifies all required network profiles are present and well-formed."""
        required = ["normal", "4g_lte", "3g_hsdpa", "2g_edge", "satellite", "congested", "packet_loss"]
        for p in required:
            self.assertIn(p, self.shaper.PROFILES)
            prof = self.shaper.PROFILES[p]
            self.assertIn("bandwidth_kbps", prof)
            self.assertIn("latency_ms", prof)
            self.assertIn("loss_pct", prof)

    def test_apply_profile_updates_active_state(self):
        """Applying profile updates internal state parameters."""
        res = self.shaper.apply_profile("2g_edge")
        self.assertEqual(res["profile_name"], "2g_edge")
        self.assertEqual(res["bandwidth_kbps"], 150.0)
        self.assertEqual(self.shaper.get_active_profile()["profile_name"], "2g_edge")

        reset_res = self.shaper.reset()
        self.assertEqual(reset_res["profile_name"], "normal")


if __name__ == "__main__":
    unittest.main()
