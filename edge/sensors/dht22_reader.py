"""
DHT22 Temperature & Humidity Sensor Reader (Raspberry Pi GPIO)

Hardware Wiring:
- VCC  -> 3.3V (Pin 1)
- DATA -> GPIO4 (Pin 7) with a 10kΩ pull-up resistor to 3.3V
- GND  -> GND (Pin 9)

Required Libraries on Raspberry Pi OS:
  pip install adafruit-circuitpython-dht
  sudo apt-get install libgpiod2
"""

from typing import Dict, Any, Optional

try:
    import board
    import adafruit_dht
    HAS_HARDWARE_LIBS = True
except ImportError:
    HAS_HARDWARE_LIBS = False


class DHT22Reader:
    """Reads physical DHT22 sensor connected to Raspberry Pi GPIO pin."""

    def __init__(self, pin=None):
        if not HAS_HARDWARE_LIBS:
            self.dht_device = None
        else:
            # Default to GPIO4 (board.D4)
            gpio_pin = pin if pin is not None else board.D4
            self.dht_device = adafruit_dht.DHT22(gpio_pin)

    def read(self) -> Dict[str, float]:
        """
        Reads temperature (°C) and relative humidity (%) from the physical DHT22 sensor.
        """
        if not self.dht_device:
            raise RuntimeError("DHT22 hardware libraries (adafruit-circuitpython-dht) not available.")

        try:
            temperature_c = self.dht_device.temperature
            humidity = self.dht_device.humidity

            if temperature_c is not None and humidity is not None:
                return {
                    "temperature_c": round(temperature_c, 2),
                    "humidity_percent": round(humidity, 2)
                }
        except RuntimeError as error:
            print(f"[DHT22 Error] Reading failed: {error.args[0]}")

        return {}
