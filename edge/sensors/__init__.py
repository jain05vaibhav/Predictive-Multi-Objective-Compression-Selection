"""
Sensors & Telemetry Package (Raspberry Pi 3B+)

Includes:
- DHT22Reader: Physical DHT22 GPIO sensor
- CameraReader: Physical CSI/USB camera module
- RPiSystemReader: Raspberry Pi 3B+ SoC thermal, electrical, and CPU telemetry (vcgencmd, psutil, /sys, /proc)
- RPiTelemetryHub: Unified live telemetry coordinator
"""

from edge.sensors.dht22_reader import DHT22Reader
from edge.sensors.camera_reader import CameraReader
from edge.sensors.rpi_system_reader import RPiSystemReader
from edge.sensors.telemetry_source import RPiTelemetryHub, TelemetrySource, SimulatedSource

__all__ = [
    "DHT22Reader",
    "CameraReader",
    "RPiSystemReader",
    "RPiTelemetryHub",
    "TelemetrySource",
    "SimulatedSource"
]
