"""
Simulated Telemetry & Sensor Source (Raspberry Pi Hardware Backup)

Phase 1 Hardware Architecture Mimicked:
--------------------------------------
1. DHT22 Sensor: Data pin -> GPIO4 (3.3V pull-up). Measures ambient Temperature (°C) & Humidity (%).
2. INA219 Sensor: I2C interface (SDA/SCL, VCC 3.3V). Measures Pi rail Voltage (V), Current (mA), & Power (mW).
3. CSI Camera Module: Captures frame data for downstream compression & transmission pipelines.

Role in Pipeline:
-----------------
Allows building, testing, and demonstrating Stage 1 to Stage 7 without blocking on physical Raspberry Pi hardware.
Toggle `USE_REAL_HARDWARE = True` when physical sensors arrive and are wired.
"""

import time
import math
import random
from typing import Dict, Any, Optional

# Configuration flag: Set to True when physical Raspberry Pi hardware is wired and ready.
# If False, or if hardware initialization fails, the backup simulation is automatically used.
USE_REAL_HARDWARE: bool = False


class SimulatedSource:
    """
    Simulates sensor telemetry (DHT22, INA219, CSI Camera) with realistic dynamic variations,
    or delegates to physical hardware readers if USE_REAL_HARDWARE is enabled.
    """

    def __init__(self, use_real_hardware: bool = USE_REAL_HARDWARE):
        self.use_real_hardware = use_real_hardware
        self.frame_counter = 0
        self.start_time = time.time()

        # Sensor reader instances for physical hardware mode
        self.real_dht22 = None
        self.real_ina219 = None
        self.real_camera = None

        if self.use_real_hardware:
            self._init_real_hardware()

    def _init_real_hardware(self) -> None:
        """Attempts to initialize physical hardware sensor modules."""
        try:
            from edge.sensors.dht22_reader import DHT22Reader
            from edge.sensors.ina219_power import INA219PowerReader
            from edge.sensors.camera_reader import CameraReader

            self.real_dht22 = DHT22Reader()
            self.real_ina219 = INA219PowerReader()
            self.real_camera = CameraReader()
        except Exception as e:
            # Fall back safely to simulation if hardware or libraries are missing
            print(f"[SimulatedSource Warning] Physical hardware setup failed ({e}). Falling back to simulation mode.")
            self.use_real_hardware = False

    def read_dht22(self) -> Dict[str, float]:
        """
        Simulates DHT22 temperature & humidity readings on GPIO4.
        Mimics natural environmental fluctuations over time.
        """
        if self.use_real_hardware and self.real_dht22:
            try:
                reading = self.real_dht22.read()
                if reading:
                    return reading
            except Exception:
                pass  # Fallback to simulated reading on hardware error

        elapsed = time.time() - self.start_time
        # Temperature oscillates realistically around ~24°C with noise
        temp_c = round(24.0 + 2.5 * math.sin(elapsed / 30.0) + random.uniform(-0.3, 0.3), 2)
        # Humidity oscillates around ~55% with noise
        humidity = round(55.0 + 5.0 * math.cos(elapsed / 45.0) + random.uniform(-0.8, 0.8), 2)

        return {
            "temperature_c": temp_c,
            "humidity_percent": humidity
        }

    def read_ina219(self) -> Dict[str, float]:
        """
        Simulates INA219 current/power monitor over I2C.
        Mimics Raspberry Pi power consumption under changing CPU load.
        """
        if self.use_real_hardware and self.real_ina219:
            try:
                reading = self.real_ina219.read_power()
                if reading:
                    return reading
            except Exception:
                pass  # Fallback to simulated reading on hardware error

        elapsed = time.time() - self.start_time
        # Baseline 5.0V power rail voltage with small ripple
        bus_voltage_v = round(5.05 + random.uniform(-0.05, 0.05), 3)
        # Dynamic current draw representing Pi CPU load variations (350mA - 650mA)
        current_ma = round(450.0 + 100.0 * math.sin(elapsed / 15.0) + random.uniform(-25.0, 25.0), 2)
        power_mw = round(bus_voltage_v * current_ma, 2)
        shunt_voltage_mv = round(current_ma * 0.1, 2)  # 0.1 ohm shunt resistor

        return {
            "voltage_v": bus_voltage_v,
            "bus_voltage_v": bus_voltage_v,
            "current_ma": current_ma,
            "power_mw": power_mw,
            "shunt_voltage_mv": shunt_voltage_mv
        }

    def read_camera(self) -> Dict[str, Any]:
        """
        Simulates CSI Camera frame acquisition.
        Generates frame count, resolution, and synthetic byte payload.
        """
        if self.use_real_hardware and self.real_camera:
            try:
                reading = self.real_camera.capture_frame()
                if reading:
                    return reading
            except Exception:
                pass  # Fallback to simulated reading on hardware error

        self.frame_counter += 1
        synthetic_payload = f"FRAME_{self.frame_counter}_PAYLOAD_TIMESTAMP_{time.time()}".encode("utf-8")

        return {
            "frame_id": self.frame_counter,
            "resolution": (640, 480),
            "format": "JPEG",
            "image_bytes": synthetic_payload,
            "size_bytes": len(synthetic_payload)
        }

    def read_all(self) -> Dict[str, Any]:
        """
        Aggregates all sensor readings (DHT22, INA219, Camera) into a single telemetry payload.
        Used by Stage 1 Data Acquisition to feed Stages 1–7 without blocking on physical hardware.
        """
        now = time.time()
        dht_data = self.read_dht22()
        ina_data = self.read_ina219()
        cam_data = self.read_camera()

        return {
            "timestamp": now,
            # Top-level direct keys for convenience in stage processing
            "temperature": dht_data["temperature_c"],
            "humidity": dht_data["humidity_percent"],
            "voltage_v": ina_data["voltage_v"],
            "current_ma": ina_data["current_ma"],
            "power_mw": ina_data["power_mw"],
            "frame_id": cam_data["frame_id"],
            "frame_data": cam_data["image_bytes"],
            # Grouped telemetry sections per sensor component
            "dht22": dht_data,
            "ina219": ina_data,
            "camera": cam_data
        }
