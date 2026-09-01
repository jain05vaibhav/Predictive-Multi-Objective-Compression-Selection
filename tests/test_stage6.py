"""
Unit Tests for Stage 6: Network Transmission & Deferral Manager
"""

import unittest
from edge.stage6_transmission import TransmissionStage


class TestStage6Transmission(unittest.TestCase):

    def setUp(self):
        self.tx = TransmissionStage(enable_network=False)
        self.dummy_payload = {
            "window_id": 1,
            "compressor_used": "lz4",
            "compression_level": 1,
            "raw_size_bytes": 1000,
            "compressed_size_bytes": 250,
            "compression_ratio": 4.0,
            "execution_time_ms": 0.5,
            "cpu_energy_proxy_uj": 1000.0,
            "compressed_payload": b"COMPRESSED_DATA_BLOB"
        }

    def test_transmit_immediate_mode(self):
        """Standard transmit action should report sent_immediate with 0 queue depth."""
        res = self.tx.transmit(self.dummy_payload, decision={"transmit_or_defer": "transmit"})
        self.assertEqual(res["status"], "sent_immediate")
        self.assertEqual(res["bytes_transmitted"], 250)
        self.assertEqual(res["queue_depth"], 0)
        self.assertEqual(self.tx.total_packets_sent, 1)

    def test_deferral_action_enqueues_payload(self):
        """When decision specifies defer, payload must be stored in FIFO backlog queue."""
        res = self.tx.transmit(self.dummy_payload, decision={"transmit_or_defer": "defer"})
        self.assertEqual(res["status"], "deferred_to_queue")
        self.assertEqual(res["bytes_transmitted"], 0)
        self.assertEqual(res["queue_depth"], 1)
        self.assertEqual(self.tx.get_queue_depth(), 1)

    def test_force_offline_buffers_to_queue(self):
        """When offline/network fails, payload is buffered rather than dropped."""
        res = self.tx.transmit(self.dummy_payload, decision={"transmit_or_defer": "transmit"}, force_offline=True)
        self.assertEqual(res["status"], "deferred_to_queue")
        self.assertEqual(self.tx.get_queue_depth(), 1)

    def test_fifo_queue_flushing_upon_recovery(self):
        """Upon link recovery, all queued backlog packets are flushed in FIFO order."""
        # Enqueue 3 packets
        for i in range(1, 4):
            item = dict(self.dummy_payload)
            item["window_id"] = i
            self.tx.transmit(item, decision={"transmit_or_defer": "defer"})

        self.assertEqual(self.tx.get_queue_depth(), 3)

        # Transmit 4th packet with 'transmit' -> triggers flush
        recovered_item = dict(self.dummy_payload)
        recovered_item["window_id"] = 4
        res = self.tx.transmit(recovered_item, decision={"transmit_or_defer": "transmit"})

        self.assertEqual(res["status"], "sent_immediate")
        self.assertEqual(res["flushed_count"], 3)
        self.assertEqual(self.tx.get_queue_depth(), 0)
        self.assertEqual(self.tx.total_packets_sent, 4)


if __name__ == "__main__":
    unittest.main()

