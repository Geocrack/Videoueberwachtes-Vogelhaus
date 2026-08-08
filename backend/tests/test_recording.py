import app as app_module


def make_client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "RECORDINGS_DIR", tmp_path)
    return app_module.app.test_client()


def test_start_and_stop_without_frames(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    assert client.post("/api/cameras/cam-a/recording/start").status_code == 200
    # Starting twice is rejected
    assert client.post("/api/cameras/cam-a/recording/start").status_code == 409

    # Stop without received frames: nothing to save
    assert client.post("/api/cameras/cam-a/recording/stop").status_code == 409
    # Stop without a running recording is rejected
    assert client.post("/api/cameras/cam-a/recording/stop").status_code == 409


def test_frames_are_saved_while_recording(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    client.post("/api/cameras/cam-b/recording/start")
    app_module.save_frame_if_recording("cam-b", b"\xff\xd8frame1")
    app_module.save_frame_if_recording("cam-b", b"\xff\xd8frame2")

    recording_dir = next((tmp_path / "cam-b").iterdir())
    assert (recording_dir / "frame_000001.jpg").read_bytes() == b"\xff\xd8frame1"
    assert (recording_dir / "frame_000002.jpg").read_bytes() == b"\xff\xd8frame2"

    app_module.recordings.pop("cam-b", None)


def test_nothing_is_saved_without_recording(tmp_path, monkeypatch):
    make_client(tmp_path, monkeypatch)

    app_module.save_frame_if_recording("cam-c", b"\xff\xd8frame")
    assert not (tmp_path / "cam-c").exists()


def test_video_list_is_empty_initially(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    response = client.get("/api/cameras/cam-d/videos")
    assert response.status_code == 200
    assert response.get_json() == {"videos": []}


def test_invalid_names_are_rejected(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    # Names with special characters do not match any route -> 404
    assert client.post("/api/cameras/cam.x/recording/start").status_code == 404
    assert client.get("/api/cameras/cam-e/videos/not-a-video.txt").status_code == 404


def test_camera_info_is_saved_and_listed(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch)

    info = {"name": "Garten", "location": "Apfelbaum", "description": "Testhaus"}
    response = client.put("/api/cameras/cam-f/info", json=info)
    assert response.status_code == 200
    assert (tmp_path / "cam-f" / "info.json").is_file()

    response = client.get("/api/cameras")
    assert response.status_code == 200
    cameras = response.get_json()["cameras"]
    camera = next(camera for camera in cameras if camera["id"] == "cam-f")
    assert {key: camera[key] for key in info} == info
    assert camera["online"] is False
