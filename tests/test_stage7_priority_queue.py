"""
Unit Tests for Phase 15: QoS-Aware Resilient Transmission & Priority Backlog
"""

import unittest
from edge.stage7_radio import RadioTransmissionStage


class TestQoSPriorityBacklog(unittest.TestCase):

    def setUp(self):
        # Create stage with 10 KB memory ceiling for testing eviction
        self.stage = RadioTransmissionStage(enable_network=False, max_buffer_bytes=10000)

    def test_priority_tier_resolution_and_ordering(self):
        """Tier 0 (Urgent) packets are drained before Tier 1 (Routine) and Tier 2 (Bulk)."""
        bulk_pkt = {"window_id": 1, "criticality": "bulk", "payload_bytes": b"BULK_DATA"}
        routine_pkt = {"window_id": 2, "criticality": "routine", "payload_bytes": b"ROUTINE_DATA"}
        urgent_pkt = {"window_id": 3, "criticality": "critical", "payload_bytes": b"URGENT_ALARM"}

        # Enqueue out of priority order: Bulk, Routine, Urgent
        self.stage.enqueue_priority(bulk_pkt)
        self.stage.enqueue_priority(routine_pkt)
        self.stage.enqueue_priority(urgent_pkt)

        self.assertEqual(self.stage.get_queue_depth(), 3)
        self.assertEqual(self.stage.get_queue_depth(tier=0), 1)
        self.assertEqual(self.stage.get_queue_depth(tier=1), 1)
        self.assertEqual(self.stage.get_queue_depth(tier=2), 1)

        # Pop should yield Urgent (Tier 0) first
        t1, p1 = self.stage.pop_highest_priority()
        self.assertEqual(t1, 0)
        self.assertEqual(p1["window_id"], 3)

        # Then Routine (Tier 1)
        t2, p2 = self.stage.pop_highest_priority()
        self.assertEqual(t2, 1)
        self.assertEqual(p2["window_id"], 2)

        # Finally Bulk (Tier 2)
        t3, p3 = self.stage.pop_highest_priority()
        self.assertEqual(t3, 2)
        self.assertEqual(p3["window_id"], 1)

        # Queue empty
        self.assertIsNone(self.stage.pop_highest_priority())
        self.assertEqual(self.stage.get_queue_depth(), 0)

    def test_memory_ceiling_eviction_protects_urgent(self):
        """When memory limit is reached, Bulk is evicted first, preserving Urgent."""
        stage_small = RadioTransmissionStage(enable_network=False, max_buffer_bytes=500)

        # Add Urgent packet (100 bytes)
        urgent = {"window_id": 1, "criticality": "critical", "payload_bytes": b"U" * 100}
        stage_small.enqueue_priority(urgent)

        # Add Routine packet (100 bytes)
        routine = {"window_id": 2, "criticality": "routine", "payload_bytes": b"R" * 100}
        stage_small.enqueue_priority(routine)

        # Add Bulk packet (250 bytes) -> total 450 bytes
        bulk = {"window_id": 3, "criticality": "bulk", "payload_bytes": b"B" * 250}
        stage_small.enqueue_priority(bulk)

        self.assertEqual(stage_small.get_queue_depth(), 3)

        # Add another packet (200 bytes) -> total would be 650 bytes (> 500 byte limit)
        # Should evict bulk packet first!
        incoming = {"window_id": 4, "criticality": "routine", "payload_bytes": b"R" * 200}
        stage_small.enqueue_priority(incoming)

        self.assertGreater(stage_small.total_evicted_packets, 0)
        # Bulk tier should be empty because it was evicted to make room
        self.assertEqual(stage_small.get_queue_depth(tier=2), 0)
        # Urgent packet MUST still be intact in Tier 0
        self.assertEqual(stage_small.get_queue_depth(tier=0), 1)
        tier, p = stage_small.pop_highest_priority()
        self.assertEqual(tier, 0)
        self.assertEqual(p["window_id"], 1)

    def test_backlog_coalescing(self):
        """Extended backlog in Tier 1 coalesces into a single high-ratio archive packet."""
        # Enqueue 6 routine packets
        for i in range(1, 7):
            pkt = {
                "window_id": i,
                "criticality": "routine",
                "raw_size_bytes": 1000,
                "compressed_size_bytes": 200,
                "payload_bytes": b"SENSOR_SAMPLE_TELEMETRY_FRAME_" * 10
            }
            self.stage.enqueue_priority(pkt)

        self.assertEqual(self.stage.get_queue_depth(tier=1), 6)

        # Run coalescing
        coalesce_res = self.stage.coalesce_backlog(min_windows=5)
        self.assertTrue(coalesce_res["coalesced"])
        self.assertEqual(coalesce_res["coalesced_count"], 6)

        # Queue depth in Tier 1 should now be 1 (the single archive packet)
        self.assertEqual(self.stage.get_queue_depth(tier=1), 1)

        t, coalesced_pkt = self.stage.pop_highest_priority()
        self.assertEqual(t, 1)
        self.assertTrue(coalesced_pkt.get("is_coalesced"))
        self.assertEqual(len(coalesced_pkt["coalesced_window_ids"]), 6)


if __name__ == "__main__":
    unittest.main()
