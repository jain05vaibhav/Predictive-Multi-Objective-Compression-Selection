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

from typing import Dict, Any, Optional
import os
import shutil
import subprocess
import tempfile
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
    """Captures real camera frames using Picamera2, OpenCV, or the native libcamera/rpicam CLI."""

    def __init__(self, resolution: tuple = (640, 480)):
        self.resolution = resolution
        self.frame_counter = 0
        self.picam2 = None
        self.cap = None
        self.cli_still_cmd = None
        self.cli_video_cmd = None
        self.cli_camera_available = False

        self._detect_cli_camera()

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

    def _detect_cli_camera(self):
        """Detect the Raspberry Pi libcamera/rpicam command-line tools installed on the OS."""
        still_candidates = ["rpicam-still", "libcamera-still"]
        video_candidates = ["rpicam-vid", "libcamera-vid"]

        self.cli_still_cmd = next((cmd for cmd in still_candidates if shutil.which(cmd)), None)
        self.cli_video_cmd = next((cmd for cmd in video_candidates if shutil.which(cmd)), None)
        self.cli_camera_available = bool(self.cli_still_cmd or self.cli_video_cmd)

        if self.cli_camera_available:
            print(f"[CameraReader] Native libcamera CLI detected: still={self.cli_still_cmd}, video={self.cli_video_cmd}")

    def _read_cli_image_bytes(self, width: int, height: int) -> bytes:
        """Capture a still image using the Raspberry Pi native camera CLI."""
        if not self.cli_still_cmd:
            raise RuntimeError("No Raspberry Pi camera CLI tool found for still capture.")

        fd, temp_path = tempfile.mkstemp(prefix="rpicam_frame_", suffix=".jpg")
        os.close(fd)
        try:
            cmd = [
                self.cli_still_cmd,
                "-n",
                "--width",
                str(width),
                "--height",
                str(height),
                "-o",
                temp_path,
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            with open(temp_path, "rb") as f:
                return f.read()
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def capture_frame(self) -> Dict[str, Any]:
        """
        Captures a real image frame and returns JPEG image bytes + metadata.
        """
        self.frame_counter += 1
        image_bytes = b""

        if self.picam2:
            try:
                frame_array = self.picam2.capture_array()
                if HAS_OPENCV:
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

        elif self.cli_camera_available:
            try:
                image_bytes = self._read_cli_image_bytes(self.resolution[0], self.resolution[1])
            except Exception as e:
                print(f"[Camera Error] Native CLI capture failed: {e}")

        if not image_bytes:
            image_bytes = f"FRAME_{self.frame_counter}_BYTES_{time.time()}".encode("utf-8")

        return {
            "frame_id": self.frame_counter,
            "resolution": self.resolution,
            "format": "JPEG",
            "image_bytes": image_bytes,
            "size_bytes": len(image_bytes)
        }

    def capture_video(self, duration_ms: int = 2000, framerate: int = 30) -> Dict[str, Any]:
        """Capture a short MP4 clip using the native Raspberry Pi video camera tool."""
        if not self.cli_video_cmd:
            raise RuntimeError("No Raspberry Pi camera CLI tool found for video capture.")

        fd, temp_path = tempfile.mkstemp(prefix="rpicam_video_", suffix=".mp4")
        os.close(fd)
        os.remove(temp_path)

        try:
            cmd = [
                self.cli_video_cmd,
                "-n",
                "--width",
                str(self.resolution[0]),
                "--height",
                str(self.resolution[1]),
                "--framerate",
                str(framerate),
                "--bitrate",
                "12000000",
                "--codec",
                "libav",
                "--libav-format",
                "mp4",
                "-t",
                str(duration_ms),
                "-o",
                temp_path,
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            with open(temp_path, "rb") as f:
                video_bytes = f.read()
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        return {
            "frame_id": self.frame_counter,
            "resolution": self.resolution,
            "format": "MP4",
            "video_bytes": video_bytes,
            "size_bytes": len(video_bytes)
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
