import os

from edge.sensors.camera_reader import CameraReader
import edge.sensors.camera_reader as camera_module


def test_capture_frame_uses_rpicam_cli_when_python_libraries_are_missing(monkeypatch, tmp_path):
    camera_module.HAS_PICAM2 = False
    camera_module.HAS_OPENCV = False

    temp_jpeg = tmp_path / "capture.jpg"
    temp_jpeg.write_bytes(b"\xff\xd8\xff\xe0JPEG_TEST_DATA")

    def fake_run(command, check=False, capture_output=False, text=False, stdout=None, stderr=None):
        assert "rpicam-still" in command
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr(camera_module, "_read_cli_image_bytes", lambda *args, **kwargs: temp_jpeg.read_bytes())
    monkeypatch.setattr(camera_module, "_cli_camera_available", lambda: True)

    reader = CameraReader()
    data = reader.capture_frame()

    assert data["format"] == "JPEG"
    assert data["image_bytes"].startswith(b"\xff\xd8\xff")
    assert data["size_bytes"] > 0
    assert not data["image_bytes"].startswith(b"FRAME_")

    reader.close()
