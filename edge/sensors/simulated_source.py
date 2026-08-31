"""
Hardware Telemetry Module (Raspberry Pi 3B+)

Provides backward-compatible exports for RPiTelemetryHub.
All simulated sensor generation has been replaced with real hardware readers:
- DHT22 (GPIO4)
- RPi 3B+ Native System Metrics (vcgencmd, psutil, Linux /sys and /proc)
- CSI / USB Camera Module
"""

from edge.sensors.telemetry_source import RPiTelemetryHub, TelemetrySource, SimulatedSource

__all__ = ["RPiTelemetryHub", "TelemetrySource", "SimulatedSource"]

if __name__ == "__main__":
    hub = RPiTelemetryHub()
    print("Telemetry Source Sample:", hub.read_all())
