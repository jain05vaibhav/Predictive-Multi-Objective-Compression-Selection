"""
End-to-End Closed-Loop Feedback Integration Test (Stages 1 through 8, Objectives O1-O5)

Verifies the complete closed-loop lifecycle:
  Edge Node (Stages 1-7) -> Live TCP Network -> Cloud Receiver (Stage 8)
  Cloud Receiver (Stage 8 Outcome Log) -> TCP ACK -> Edge Profiler (Stage 4, O4) & Bandit (Stage 5, O3)
"""

import os
import time
import socket
import unittest

from edge.main_loop import EdgePipeline
from cloud.receiver import CloudReceiver


class TestClosedLoopFeedback(unittest.TestCase):

    def setUp(self):
        self.cloud_port = 8799
        self.test_cloud_log = "logs/test_e2e_cloud_outcomes.csv"
        self.test_dec_log = "logs/test_e2e_decisions.csv"

        # Start background cloud receiver
        self.receiver = CloudReceiver(
            host="127.0.0.1",
            port=self.cloud_port,
            log_file=self.test_cloud_log
        )
        self.receiver.start_socket_server(blocking=False)
        time.sleep(0.1)  # Allow socket bind

        # Sample data pool for deterministic testing
        self.sample_pool = [
            {
                "temperature": 23.5, "humidity": 60.0,
                "system": {"cpu_temp_c": 41.0, "cpu_percent": 12.0, "core_voltage_v": 1.25}
            }
            for _ in range(20)
        ]

        self.pipeline = EdgePipeline(
            window_size=5,
            cloud_host="127.0.0.1",
            cloud_port=self.cloud_port,
            source=self.sample_pool
        )
        self.pipeline.stage5.log_file = self.test_dec_log

    def tearDown(self):
        self.receiver.stop_server()
        time.sleep(0.05)
        for f in [self.test_cloud_log, self.test_dec_log]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

    def test_end_to_end_closed_loop_execution_and_feedback(self):
        """
        Executes an end-to-end window cycle over live TCP socket and verifies
        that Stage 8 outcome log is returned and updates Stage 4 and Stage 5!
        """
        cycle_result = self.pipeline.run_window_cycle()

        self.assertEqual(cycle_result["cycle"], 1)
        self.assertEqual(cycle_result["window"].sample_count, 5)

        # Verify Stage 7 transmitted successfully
        tx = cycle_result["transmission"]
        self.assertEqual(tx["status"], "sent_immediate")
        self.assertEqual(tx["radio_state"], "ACTIVE")

        # Verify Stage 8 feedback was received back at the edge
        feedback = tx.get("feedback_outcome")
        self.assertIsNotNone(feedback)
        self.assertEqual(feedback["status"], "verified")
        self.assertIn("ratio", feedback)
        self.assertIn("error", feedback)

        # Verify Stage 4 Profiler calibration table absorbed update (Objective O4)
        profiler_upd = cycle_result.get("profiler_update")
        self.assertIsNotNone(profiler_upd)
        self.assertGreater(profiler_upd.get("updates_count", 0), 0)

        # Verify Stage 5 Contextual Bandit absorbed update (Objective O3)
        bandit_upd = cycle_result.get("bandit_update")
        self.assertIsNotNone(bandit_upd)
        self.assertIn("score_error", bandit_upd)


if __name__ == "__main__":
    unittest.main()
