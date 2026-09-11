# Tests for the camera status: online detection, the stored state and the order of the camera list.

import json
from io import BytesIO

from PIL import Image

import app as app_module


def make_client(tmp_path, monkeypatch):
    # Gives a test client with an empty recordings folder and no remembered cameras.
    monkeypatch.setattr(app_module, "RECORDINGS_DIR", tmp_path)
    monkeypatch.setattr(app_module, "camera_state", {})
    return app_module.app.test_client()


def jpeg_frame():
    # Gives a small JPEG with a known size.
    buffer = BytesIO()
    Image.new("RGB", (320, 240), "green").save(buffer, "JPEG")
    return buffer.getvalue()


def get_camera(client, camera_id):
    # Gives the entry of one camera from the camera list, or None if it is not listed.
    cameras = client.get("/api/cameras").get_json()["cameras"]
    for camera in cameras:
        if camera["id"] == camera_id:
            return camera
    return None


def write_stored_state(tmp_path, camera_id, last_seen):
    # Writes a state.json as the backend leaves it behind after a camera disconnects.
    folder = tmp_path / camera_id
    folder.mkdir(parents=True)
    stored = {"last_seen": last_seen, "width": 320, "height": 240}
    (folder / "state.json").write_text(json.dumps(stored), encoding="utf-8")


def test_camera_is_online_only_while_frames_arrive(tmp_path, monkeypatch):
    # Tests that a camera is online after its first frame, offline after the timeout and after the disconnect.
    client = make_client(tmp_path, monkeypatch)
    monkeypatch.setattr(app_module, "ONLINE_TIMEOUT_SECONDS", 15)

    app_module.note_camera_connected("cam-p")
    # Connected, but no frame yet: the camera is listed, but not online
    camera = get_camera(client, "cam-p")
    assert camera is not None
    assert camera["online"] is False

    app_module.note_frame("cam-p", jpeg_frame())
    camera = get_camera(client, "cam-p")
    assert camera["online"] is True
    assert camera["last_seen"] is not None
    assert camera["width"] == 320
    assert camera["height"] == 240

    # The connection is still open, but no frames arrive any more
    app_module.camera_state["cam-p"]["last_frame_at"] -= 16
    assert get_camera(client, "cam-p")["online"] is False

    app_module.note_frame("cam-p", jpeg_frame())
    assert get_camera(client, "cam-p")["online"] is True

    app_module.note_camera_disconnected("cam-p")
    assert get_camera(client, "cam-p")["online"] is False


def test_state_and_poster_survive_a_restart(tmp_path, monkeypatch):
    # Tests that last_seen, size and the last frame are kept on disk and listed after a restart.
    client = make_client(tmp_path, monkeypatch)

    app_module.note_camera_connected("cam-r")
    app_module.note_frame("cam-r", jpeg_frame())
    last_frame = jpeg_frame()
    app_module.note_camera_disconnected("cam-r", last_frame)

    stored = json.loads((tmp_path / "cam-r" / "state.json").read_text(encoding="utf-8"))
    assert stored["last_seen"] is not None
    assert (tmp_path / "cam-r" / "poster.jpg").read_bytes() == last_frame

    # A restart forgets the in-memory state, the list still shows the stored values
    monkeypatch.setattr(app_module, "camera_state", {})
    camera = get_camera(client, "cam-r")
    assert camera["online"] is False
    assert camera["last_seen"] == stored["last_seen"]
    assert camera["width"] == 320
    assert camera["height"] == 240
    assert camera["has_poster"] is True
    assert client.get("/api/cameras/cam-r/poster.jpg").data == last_frame


def test_cameras_are_sorted_online_first_then_by_last_seen(tmp_path, monkeypatch):
    # Tests the order of the list: online cameras first, then the most recently seen, unknown last.
    client = make_client(tmp_path, monkeypatch)

    write_stored_state(tmp_path, "cam-old", "2026-01-01T10:00:00+01:00")
    write_stored_state(tmp_path, "cam-new", "2026-02-01T10:00:00+01:00")
    (tmp_path / "cam-never").mkdir()
    app_module.note_camera_connected("cam-live")
    app_module.note_frame("cam-live", jpeg_frame())

    cameras = client.get("/api/cameras").get_json()["cameras"]
    ids = []
    for camera in cameras:
        ids.append(camera["id"])
    assert ids == ["cam-live", "cam-new", "cam-old", "cam-never"]
