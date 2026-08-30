"""
INA219 I2C Voltage, Current, and Power Sensor Reader

Hardware Wiring:
- VCC -> 3.3V (Pin 1)
- GND -> GND (Pin 6)
- SDA -> GPIO2 (SDA1, Pin 3)
- SCL -> GPIO3 (SCL1, Pin 5)

Required Libraries on Raspberry Pi OS:
  sudo raspi-config  # Enable I2C under Interface Options
  pip install adafruit-circuitpython-ina219
"""

from typing import Dict, Any

try:
    import board
    import busio
    from adafruit_ina219 import INA219
    HAS_HARDWARE_LIBS = True
except ImportError:
    HAS_HARDWARE_LIBS = False


class INA219PowerReader:
    """Reads physical INA219 sensor over I2C to measure voltage, current, and power draw."""

    def __init__(self, i2c_address: int = 0x40):
        if not HAS_HARDWARE_LIBS:
            self.ina219 = None
        else:
            try:
                i2c = busio.I2C(board.SCL, board.SDA)
                self.ina219 = INA219(i2c, addr=i2c_address)
            except Exception as e:
                print(f"[INA219 Init Error] Could not initialize I2C bus: {e}")
                self.ina219 = None

    def read_power(self) -> Dict[str, float]:
        """
        Reads voltage (V), current (mA), and power (mW) from INA219.
        """
        if not self.ina219:
            raise RuntimeError("INA219 hardware libraries or I2C bus not available.")

        bus_voltage = self.ina219.bus_voltage        # Voltage on V- (V)
        shunt_voltage = self.ina219.shunt_voltage    # Voltage across shunt (V)
        current_ma = self.ina219.current             # Current in mA
        power_mw = self.ina219.power                 # Power in mW

        return {
            "voltage_v": round(bus_voltage, 3),
            "bus_voltage_v": round(bus_voltage, 3),
            "shunt_voltage_mv": round(shunt_voltage * 1000, 2),
            "current_ma": round(current_ma, 2),
            "power_mw": round(power_mw, 2)
        }
