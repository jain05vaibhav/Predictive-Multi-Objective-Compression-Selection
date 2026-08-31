import io
import unittest
from unittest.mock import patch

from edge.sensors.camera_reader import CameraReader
import edge.sensors.camera_reader as camera_module
from edge.sensors.simulated_source import SimulatedSource


class TestCameraReader(unittest.TestCase):

    def test_save_photo_in_memory_returns_bytes_and_stream(self):
        """Verify that capture_frame and save_photo_in_memory store photo in RAM without disk I/O."""
        reader = CameraReader()
        frame = reader.save_photo_in_memory()

        self.assertIn("image_bytes", frame)
        self.assertIn("memory_buffer", frame)
        self.assertIsInstance(frame["image_bytes"], bytes)
        self.assertIsInstance(frame["memory_buffer"], io.BytesIO)
        self.assertGreater(frame["size_bytes"], 0)

        # Test in-memory buffer getter
        stream = reader.get_in_memory_buffer()
        self.assertIsInstance(stream, io.BytesIO)
        read_bytes = stream.read()
        self.assertEqual(read_bytes, frame["image_bytes"])

        reader.close()

    def test_simulated_source_in_memory_camera_buffer(self):
        """Verify SimulatedSource provides in-memory BytesIO camera buffer."""
        source = SimulatedSource(use_real_hardware=False)
        sample = source.read_all()
        cam = sample["camera"]

        self.assertIn("image_bytes", cam)
        self.assertIsInstance(cam["image_bytes"], bytes)

        buf = source.get_camera_in_memory_buffer()
        self.assertIsInstance(buf, io.BytesIO)
        self.assertEqual(buf.read(), cam["image_bytes"])

    def test_capture_frame_uses_rpicam_cli_when_python_libraries_are_missing(self):
        """Test fallback to native CLI when Picamera2 and OpenCV are not loaded."""
        with patch.object(camera_module, "HAS_PICAM2", False), \
             patch.object(camera_module, "HAS_OPENCV", False), \
             patch.object(CameraReader, "_read_cli_image_bytes", return_value=b"\xff\xd8\xff\xe0JPEG_TEST_DATA"), \
             patch.object(CameraReader, "_detect_cli_camera", lambda self: setattr(self, "cli_camera_available", True)):
            
            reader = CameraReader()
            data = reader.capture_frame()

            self.assertEqual(data["format"], "JPEG")
            self.assertTrue(data["image_bytes"].startswith(b"\xff\xd8\xff"))
            self.assertGreater(data["size_bytes"], 0)
            self.assertFalse(data["image_bytes"].startswith(b"FRAME_"))
            
            # Verify stream
            stream = reader.get_in_memory_buffer()
            self.assertEqual(stream.read(), b"\xff\xd8\xff\xe0JPEG_TEST_DATA")

    def test_save_photo_overwrites_in_destination_folder(self):
        """Verify that photos are written and overwritten in the configured output directory."""
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as tmp_dir:
            reader = CameraReader(output_dir=tmp_dir, save_to_disk=True)
            
            # First capture
            frame1 = reader.capture_frame()
            dest_file = os.path.join(tmp_dir, "latest_frame.jpg")
            self.assertTrue(os.path.exists(dest_file))
            self.assertEqual(frame1["saved_path"], os.path.abspath(dest_file))
            
            # Read first content
            with open(dest_file, "rb") as f:
                content1 = f.read()
            self.assertEqual(content1, frame1["image_bytes"])

            # Explicit save_photo overwrite
            saved_path = reader.save_photo()
            self.assertEqual(saved_path, os.path.abspath(dest_file))
            self.assertTrue(os.path.exists(dest_file))

            reader.close()


if __name__ == "__main__":
    unittest.main()


