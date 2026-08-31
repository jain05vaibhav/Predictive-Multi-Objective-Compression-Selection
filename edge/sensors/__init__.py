"""
Sensors & Telemetry Package (Raspberry Pi 3B+)

Provides on-demand imports for hardware drivers and telemetry hub:
- DHT22Reader: Physical DHT22 GPIO sensor driver
- CameraReader: CSI/USB camera module reader
- RPiSystemReader: Raspberry Pi 3B+ SoC metrics reader
- RPiTelemetryHub: Unified live hardware telemetry hub
"""

from typing import Any

__all__ = [
    "DHT22Reader",
    "CameraReader",
    "RPiSystemReader",
    "RPiTelemetryHub",
    "TelemetrySource",
    "SimulatedSource"
]


def __getattr__(name: str) -> Any:
    if name == "DHT22Reader":
        from edge.sensors.dht22_reader import DHT22Reader
        return DHT22Reader
    elif name == "CameraReader":
        from edge.sensors.camera_reader import CameraReader
        return CameraReader
    elif name == "RPiSystemReader":
        from edge.sensors.rpi_system_reader import RPiSystemReader
        return RPiSystemReader
    elif name == "RPiTelemetryHub":
        from edge.sensors.telemetry_source import RPiTelemetryHub
        return RPiTelemetryHub
    elif name == "TelemetrySource":
        from edge.sensors.telemetry_source import TelemetrySource
        return TelemetrySource
    elif name == "SimulatedSource":
        from edge.sensors.telemetry_source import SimulatedSource
        return SimulatedSource
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
