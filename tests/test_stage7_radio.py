"""
Unit Tests for Stage 7: Radio Duty-Cycle & Transmission Co-Scheduler (Objective O5)
"""

import unittest
from edge.stage7_radio import RadioTransmissionStage


class TestStage7Radio(unittest.TestCase):

    def setUp(self):
        self.stage7 = RadioTransmissionStage(enable_network=False)
        self.dummy_payload = {
            "window_id": 1,
            "compressor_used": "lz4",
            "compression_level": 1,
            "raw_size_bytes": 1000,
            "compressed_size_bytes": 250,
            "compression_ratio": 4.0,
            "execution_time_ms": 0.5,
            "cpu_energy_proxy_uj": 100.0,
            "local_reconstruction_error": 0.0,
            "compressed_payload": b"PACKET_BLOB_BYTE_STREAM"
        }

    def test_joint_transmit_decision_activates_radio(self):
        """When transmit action selected, radio reports ACTIVE state and measures wake time."""
        res = self.stage7.transmit(
            self.dummy_payload,
            decision={"transmit_or_defer": "transmit", "radio_sleep_duration_s": 0.2}
        )
        self.assertEqual(res["status"], "sent_immediate")
        self.assertEqual(res["radio_state"], "ACTIVE")
        self.assertGreater(res["radio_wake_time_ms"], 0.0)
        self.assertEqual(res["queue_depth"], 0)

    def test_joint_deferral_decision_puts_radio_to_sleep(self):
        """When deferral action selected, radio reports SLEEP state and saves radio energy."""
        res = self.stage7.transmit(
            self.dummy_payload,
            decision={"transmit_or_defer": "defer", "radio_sleep_duration_s": 2.5}
        )
        self.assertEqual(res["status"], "deferred_to_queue")
        self.assertEqual(res["radio_state"], "SLEEP")
        self.assertEqual(res["radio_wake_time_ms"], 0.0)
        self.assertGreater(res["radio_energy_saved_uj"], 0.0)
        self.assertEqual(res["queue_depth"], 1)

    def test_duty_cycle_percentage_calculation(self):
        """Verifies radio duty cycle ratio calculation across active and sleep periods."""
        # Send one active packet
        self.stage7.transmit(self.dummy_payload, decision={"transmit_or_defer": "transmit"})
        # Sleep two windows
        self.stage7.transmit(self.dummy_payload, decision={"transmit_or_defer": "defer", "radio_sleep_duration_s": 1.0})
        self.stage7.transmit(self.dummy_payload, decision={"transmit_or_defer": "defer", "radio_sleep_duration_s": 1.0})

        # Send another active packet
        res = self.stage7.transmit(self.dummy_payload, decision={"transmit_or_defer": "transmit"})
        self.assertIn("duty_cycle_percent", res)
        # Sleep dominates wake time -> duty cycle should be low (< 10%)
        self.assertLess(res["duty_cycle_percent"], 10.0)


if __name__ == "__main__":
    unittest.main()
