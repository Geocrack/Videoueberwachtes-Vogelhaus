from io import BytesIO

from PIL import Image

import app as app_module


def make_client(tmp_path, monkeypatch):
    # Gives a test client whose recordings land in an empty temporary folder.
    monkeypatch.setattr(app_module, "RECORDINGS_DIR", tmp_path)
    return app_module.app.test_client()


def jpeg_frame():
    # Gives a small JPEG that ffmpeg can decode.
    buffer = BytesIO()
    Image.new("RGB", (64, 48), "green").save(buffer, "JPEG")
    return buffer.getvalue()


def record_video(client, camera_id, name=None):
    # Runs a complete recording and gives back the file name of the resulting MP4.
    client.post(f"/api/cameras/{camera_id}/recording/start")
    for _ in range(3):
        app_module.save_frame_if_recording(camera_id, jpeg_frame())

    payload = {} if name is None else {"name": name}
    response = client.post(f"/api/cameras/{camera_id}/recording/stop", json=payload)
    assert response.status_code == 200
    return response.get_json()["video"]


def test_start_and_stop_without_frames(tmp_path, monkeypatch):
    # Tests that only one recording per camera runs and that one without frames saves nothing.
    client = make_client(tmp_path, monkeypatch)

    assert client.post("/api/cameras/cam-a/recording/start").status_code == 200
    # Starting twice is rejected
    assert client.post("/api/cameras/cam-a/recording/start").status_code == 409

    # Stop without received frames: nothing to save
    assert client.post("/api/cameras/cam-a/recording/stop").status_code == 409
    # Stop without a running recording is rejected
    assert client.post("/api/cameras/cam-a/recording/stop").status_code == 409


def test_frames_are_saved_while_recording(tmp_path, monkeypatch):
    # Tests that every frame lands on disk immediately, numbered consecutively from one.
    client = make_client(tmp_path, monkeypatch)

    client.post("/api/cameras/cam-b/recording/start")
    app_module.save_frame_if_recording("cam-b", b"\xff\xd8frame1")
    app_module.save_frame_if_recording("cam-b", b"\xff\xd8frame2")

    recording_dir = next((tmp_path / "cam-b").iterdir())
    assert (recording_dir / "frame_000001.jpg").read_bytes() == b"\xff\xd8frame1"
    assert (recording_dir / "frame_000002.jpg").read_bytes() == b"\xff\xd8frame2"

    app_module.recordings.pop("cam-b", None)


def test_nothing_is_saved_without_recording(tmp_path, monkeypatch):
    # Tests that frames are dropped while no recording runs, without creating a folder.
    make_client(tmp_path, monkeypatch)

    app_module.save_frame_if_recording("cam-c", b"\xff\xd8frame")
    assert not (tmp_path / "cam-c").exists()


def test_video_list_is_empty_initially(tmp_path, monkeypatch):
    # Tests that a camera without recordings answers with an empty list instead of an error.
    client = make_client(tmp_path, monkeypatch)

    response = client.get("/api/cameras/cam-d/videos")
    assert response.status_code == 200
    assert response.get_json() == {"videos": []}


def test_recording_is_saved_with_the_given_name(tmp_path, monkeypatch):
    # Tests that the name given when stopping shows up as the trimmed title in the video list.
    client = make_client(tmp_path, monkeypatch)

    video_name = record_video(client, "cam-g", "  Blaumeise am Futterhaus  ")

    videos = client.get("/api/cameras/cam-g/videos").get_json()["videos"]
    assert [(video["name"], video["title"]) for video in videos] == [
        (video_name, "Blaumeise am Futterhaus")
    ]
    assert videos[0]["size"] > 0
    assert videos[0]["created"].startswith(video_name[:10])


def test_video_can_be_renamed_afterwards(tmp_path, monkeypatch):
    # Tests that a video can be given a title later and that an empty name removes it again.
    client = make_client(tmp_path, monkeypatch)

    video_name = record_video(client, "cam-h")
    stem = video_name.removesuffix(".mp4")
    assert client.get("/api/cameras/cam-h/videos").get_json()["videos"][0]["title"] == ""

    response = client.put(f"/api/cameras/cam-h/videos/{stem}/name", json={"name": "Kohlmeise"})
    assert response.status_code == 200
    assert client.get("/api/cameras/cam-h/videos").get_json()["videos"][0]["title"] == "Kohlmeise"

    client.put(f"/api/cameras/cam-h/videos/{stem}/name", json={"name": "   "})
    assert client.get("/api/cameras/cam-h/videos").get_json()["videos"][0]["title"] == ""


def test_video_can_be_deleted(tmp_path, monkeypatch):
    # Tests that deleting removes file, list entry and title, and that a second one finds nothing.
    client = make_client(tmp_path, monkeypatch)

    video_name = record_video(client, "cam-j", "Specht")
    stem = video_name.removesuffix(".mp4")

    assert client.delete(f"/api/cameras/cam-j/videos/{stem}").status_code == 200
    assert client.get("/api/cameras/cam-j/videos").get_json()["videos"] == []
    assert not (tmp_path / "cam-j" / video_name).exists()
    assert video_name not in app_module.read_video_names("cam-j")

    assert client.delete(f"/api/cameras/cam-j/videos/{stem}").status_code == 404


def test_renaming_an_unknown_video_is_rejected(tmp_path, monkeypatch):
    # Tests that a title is only stored for a video that exists.
    client = make_client(tmp_path, monkeypatch)

    response = client.put("/api/cameras/cam-i/videos/2026-01-01_00-00-00/name", json={"name": "x"})
    assert response.status_code == 404


def test_recording_is_stopped_when_the_time_limit_is_reached(tmp_path, monkeypatch):
    # Tests that a recording running too long is reported as overdue and saved automatically.
    client = make_client(tmp_path, monkeypatch)
    monkeypatch.setattr(app_module, "MAX_RECORDING_SECONDS", 60)

    client.post("/api/cameras/cam-k/recording/start")
    for _ in range(3):
        app_module.save_frame_if_recording("cam-k", jpeg_frame())

    assert app_module.overdue_recordings() == []

    app_module.recordings["cam-k"]["started_at"] -= 61
    assert app_module.overdue_recordings() == [("cam-k", "time limit reached")]

    app_module.stop_overdue_recordings()
    assert "cam-k" not in app_module.recordings
    assert len(client.get("/api/cameras/cam-k/videos").get_json()["videos"]) == 1


def test_recording_is_stopped_when_the_frame_limit_is_reached(tmp_path, monkeypatch):
    # Tests that a recording with too many frames is reported as overdue and saved automatically.
    client = make_client(tmp_path, monkeypatch)
    monkeypatch.setattr(app_module, "MAX_RECORDING_FRAMES", 3)

    client.post("/api/cameras/cam-l/recording/start")
    for _ in range(3):
        app_module.save_frame_if_recording("cam-l", jpeg_frame())

    assert app_module.overdue_recordings() == [("cam-l", "frame limit reached")]

    app_module.stop_overdue_recordings()
    assert "cam-l" not in app_module.recordings
    assert len(client.get("/api/cameras/cam-l/videos").get_json()["videos"]) == 1


def test_recording_is_stopped_and_refused_when_disk_is_full(tmp_path, monkeypatch):
    # Tests that a running recording is saved when the disk runs full and no new one starts.
    client = make_client(tmp_path, monkeypatch)

    client.post("/api/cameras/cam-m/recording/start")
    for _ in range(3):
        app_module.save_frame_if_recording("cam-m", jpeg_frame())

    monkeypatch.setattr(app_module, "free_disk_mb", lambda: 1.0)
    assert app_module.overdue_recordings() == [("cam-m", "free disk space is running out")]

    app_module.stop_overdue_recordings()
    assert "cam-m" not in app_module.recordings

    assert client.post("/api/cameras/cam-m/recording/start").status_code == 507


def test_unwritable_frames_do_not_break_the_camera_connection(tmp_path, monkeypatch):
    # Tests that a frame which cannot be written does not raise and does not use up a number.
    client = make_client(tmp_path, monkeypatch)

    client.post("/api/cameras/cam-n/recording/start")
    app_module.recordings["cam-n"]["dir"] = tmp_path / "cam-n" / "gone"

    app_module.save_frame_if_recording("cam-n", jpeg_frame())

    assert app_module.recordings["cam-n"]["frame_number"] == 0
    app_module.recordings.pop("cam-n", None)


def test_interrupted_recording_is_recovered(tmp_path, monkeypatch):
    # Tests that frame folders left over after a crash become videos and empty ones are removed.
    client = make_client(tmp_path, monkeypatch)

    client.post("/api/cameras/cam-o/recording/start")
    for _ in range(3):
        app_module.save_frame_if_recording("cam-o", jpeg_frame())

    frames_dir = app_module.recordings.pop("cam-o")["dir"]
    empty_dir = tmp_path / "cam-o" / "2020-01-01_00-00-00"
    empty_dir.mkdir(parents=True)

    app_module.recover_interrupted_recordings()

    assert not frames_dir.exists()
    assert not empty_dir.exists()
    videos = client.get("/api/cameras/cam-o/videos").get_json()["videos"]
    assert [video["name"] for video in videos] == [f"{frames_dir.name}.mp4"]


def test_invalid_names_are_rejected(tmp_path, monkeypatch):
    # Tests that names from the URL cannot point out of the recordings folder.
    client = make_client(tmp_path, monkeypatch)

    # Names with special characters do not match any route -> 404
    assert client.post("/api/cameras/cam.x/recording/start").status_code == 404
    assert client.get("/api/cameras/cam-e/videos/not-a-video.txt").status_code == 404


def test_camera_info_is_saved_and_listed(tmp_path, monkeypatch):
    # Tests that camera info is stored and listed, and a camera without a connection is offline.
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
