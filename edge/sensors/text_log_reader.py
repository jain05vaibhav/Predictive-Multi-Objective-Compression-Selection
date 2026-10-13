"""
Edge Text & Application Log Reader (Phase 13 Multi-Modal Stream Parity)

Generates continuous streams of semi-structured text data (system logs, syslog,
application events, JSON audit trails) to evaluate text compression codecs
alongside numeric telemetry and camera streams.
"""

import time
import random
from typing import Dict, Any, List, Optional


class TextLogReader:
    """
    Simulates or streams real-time edge application and system logs.
    """

    LOG_SERVICES = ["kernel", "systemd", "edge_agent", "sensor_hub", "wpa_supplicant", "nginx"]
    LOG_LEVELS = ["INFO", "WARNING", "ERROR", "DEBUG"]

    SAMPLE_MESSAGES = [
        "Connection established to cloud receiver endpoint at port 8765",
        "Sensor DHT22 read cycle completed: temp=23.4C, hum=58.2%",
        "Thermal throttling warning: CPU frequency throttled to 600 MHz",
        "Battery voltage nominal at 3.85V, discharge rate 320mA",
        "Memory compaction triggered: freed 1420 KB in user heap",
        "Packet framed with 4-byte header: transmitted 850 bytes over TCP",
        "Buffer queue backlog depth: 3 items queued during network jitter",
        "Contextual bandit parameter theta update converged with score_error=0.012",
        "Frame grab from CSI camera module OV5647 completed in 18ms"
    ]

    def __init__(self, service_name: Optional[str] = None):
        self.service_name = service_name
        self.line_counter = 0

    def generate_log_entry(self) -> Dict[str, Any]:
        """Generates a structured log dictionary entry."""
        self.line_counter += 1
        service = self.service_name or random.choice(self.LOG_SERVICES)
        level = random.choice(self.LOG_LEVELS)
        msg = random.choice(self.SAMPLE_MESSAGES)
        ts = time.time()

        raw_line = f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))} [{level}] {service}: {msg} (seq={self.line_counter})\n"

        return {
            "seq": self.line_counter,
            "timestamp": ts,
            "service": service,
            "level": level,
            "message": msg,
            "raw_text": raw_line
        }

    def read(self) -> Dict[str, Any]:
        """TelemetrySource compatible reader method."""
        return self.generate_log_entry()

    def read_all(self) -> Dict[str, Any]:
        """RPiTelemetryHub compatible reader method."""
        return self.generate_log_entry()

    def read_batch(self, n: int = 10) -> List[Dict[str, Any]]:
        """Reads a batch of n consecutive log lines."""
        return [self.generate_log_entry() for _ in range(max(1, n))]

    def read_text_block(self, lines: int = 10) -> str:
        """Returns concatenated raw string lines."""
        return "".join(entry["raw_text"] for entry in self.read_batch(lines))
