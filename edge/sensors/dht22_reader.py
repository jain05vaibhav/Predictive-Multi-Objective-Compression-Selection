"""
DHT22 Temperature & Humidity Sensor Reader (Raspberry Pi GPIO)

Hardware Wiring:
- VCC  -> 3.3V (Pin 1)
- DATA -> GPIO4 (Pin 7) with a 10kΩ pull-up resistor to 3.3V
- GND  -> GND (Pin 9)

Required Libraries on Raspberry Pi OS:
  pip install adafruit-circuitpython-dht
  sudo apt-get install -y libgpiod2
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
        self.dht_device = None
        if HAS_HARDWARE_LIBS:
            try:
                # Default to GPIO4 (board.D4)
                gpio_pin = pin if pin is not None else board.D4
                self.dht_device = adafruit_dht.DHT22(gpio_pin)
            except Exception:
                self.dht_device = None

    def read(self) -> Dict[str, float]:
        """
        Reads temperature (°C) and relative humidity (%) from the physical DHT22 sensor.
        Returns empty dict on transient read errors (common in single-wire pulse sensors) or if unattached.
        """
        if not self.dht_device:
            return {}

        try:
            temperature_c = self.dht_device.temperature
            humidity = self.dht_device.humidity

            if temperature_c is not None and humidity is not None:
                return {
                    "temperature_c": round(temperature_c, 2),
                    "humidity_percent": round(humidity, 2)
                }
        except Exception:
            pass

        return {}

    def close(self):
        """Releases GPIO hardware line."""
        if self.dht_device:
            try:
                self.dht_device.exit()
            except Exception:
                pass
            self.dht_device = None


if __name__ == "__main__":
    print("=== Testing DHT22 Hardware Reader on Raspberry Pi ===")
    reader = DHT22Reader()
    data = reader.read()
    if data:
        print(f"Temperature: {data.get('temperature_c', 'N/A')} °C")
        print(f"Humidity:    {data.get('humidity_percent', 'N/A')} %")
    else:
        print("DHT22 sensor not responding (check 3.3V, GPIO4 pin 7, GND, and 10k pull-up resistor).")
    reader.close()
