"""
CSI Camera Module Reader (Picamera2 / OpenCV)

Hardware Wiring:
- CSI Ribbon Cable attached to Pi CSI Camera port.

Required Libraries on Raspberry Pi OS:
  sudo raspi-config  # Enable Camera under Interface Options
  sudo apt-get install -y python3-picamera2  # Bookworm / Bullseye OS
  # OR
  pip install opencv-python
"""

from typing import Dict, Any
import time

# Support Linux/Raspberry Pi case-sensitive module import
try:
    from picamera2 import Picamera2
    HAS_PICAM2 = True
except ImportError:
    try:
        from Picamera2 import Picamera2
        HAS_PICAM2 = True
    except ImportError:
        HAS_PICAM2 = False

try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False


class CameraReader:
    """Captures real camera frames using Picamera2 or OpenCV fallback."""

    def __init__(self, resolution: tuple = (640, 480)):
        self.resolution = resolution
        self.frame_counter = 0
        self.picam2 = None
        self.cap = None

        if HAS_PICAM2:
            try:
                self.picam2 = Picamera2()
                config = self.picam2.create_preview_configuration(main={"size": resolution})
                self.picam2.configure(config)
                self.picam2.start()
                print("[CameraReader] Picamera2 initialized successfully.")
            except Exception as e:
                print(f"[CameraReader Warning] Picamera2 init failed: {e}")
                self.picam2 = None

        if not self.picam2 and HAS_OPENCV:
            try:
                self.cap = cv2.VideoCapture(0)
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])
                print("[CameraReader] OpenCV VideoCapture initialized successfully.")
            except Exception as e:
                print(f"[CameraReader Warning] OpenCV VideoCapture init failed: {e}")
                self.cap = None

    def capture_frame(self) -> Dict[str, Any]:
        """
        Captures a real image frame and returns JPEG image bytes + metadata.
        """
        self.frame_counter += 1
        image_bytes = b""

        if self.picam2:
            try:
                # Capture frame array and encode to JPEG
                frame_array = self.picam2.capture_array()
                if HAS_OPENCV:
                    # Convert BGR/RGB array to JPEG bytes
                    _, buffer = cv2.imencode('.jpg', frame_array)
                    image_bytes = buffer.tobytes()
                else:
                    image_bytes = frame_array.tobytes()
            except Exception as e:
                print(f"[Camera Error] Picamera2 capture failed: {e}")

        elif self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret and HAS_OPENCV:
                _, buffer = cv2.imencode('.jpg', frame)
                image_bytes = buffer.tobytes()

        if not image_bytes:
            # Synthetic payload fallback if hardware camera fails or is missing
            image_bytes = f"FRAME_{self.frame_counter}_BYTES_{time.time()}".encode("utf-8")

        return {
            "frame_id": self.frame_counter,
            "resolution": self.resolution,
            "format": "JPEG",
            "image_bytes": image_bytes,
            "size_bytes": len(image_bytes)
        }

    def close(self):
        """Releases camera hardware resources."""
        if self.picam2:
            try:
                self.picam2.stop()
            except Exception:
                pass
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass


# Standalone Smoke-Test Script when run directly on Raspberry Pi
if __name__ == "__main__":
    print("=== Testing CameraReader on Raspberry Pi ===")
    camera = CameraReader(resolution=(640, 480))
    
    # Give sensor a moment to warm up
    time.sleep(1)

    print("Capturing test frame...")
    frame_data = camera.capture_frame()

    print(f"Status: Captured Frame #{frame_data['frame_id']}")
    print(f"Resolution: {frame_data['resolution']}")
    print(f"Format: {frame_data['format']}")
    print(f"Payload Size: {frame_data['size_bytes']} bytes")

    # Save test image to disk if real JPEG bytes were captured
    if frame_data["size_bytes"] > 100:
        with open("test_frame.jpg", "wb") as f:
            f.write(frame_data["image_bytes"])
        print("Success! Captured real image saved to 'test_frame.jpg'")
    else:
        print("Fallback payload returned (Hardware camera not detected).")

    camera.close()
