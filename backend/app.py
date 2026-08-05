import os
import re
import shutil
import subprocess
import threading
from datetime import datetime
from pathlib import Path

from flask import Flask, abort, jsonify, send_file
from flask_sock import Sock

app = Flask(__name__)
sock = Sock(app)

INDEX_HTML = Path(__file__).resolve().parent.parent / "index.html"
RECORDINGS_DIR = Path(os.environ.get("RECORDINGS_DIR", Path(__file__).resolve().parent / "recordings"))

state_lock = threading.Lock()
live_clients = {}  # camera_id -> set of connected live viewer websockets
recordings = {}    # camera_id -> {"dir": folder of the running recording, "frame_number": int}


def check_name(name):
    # Only allow simple names so nobody can escape the recordings
    # folder via the URL (e.g. camera_id = "..")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        abort(400)


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.get("/")
def index():
    return send_file(INDEX_HTML)


@sock.route("/ws/camera/<camera_id>")
def camera(ws, camera_id):
    check_name(camera_id)
    print(f"Camera {camera_id} connected")
    while True:
        data = ws.receive()
        if data is None:
            break

        if isinstance(data, bytes):
            save_frame_if_recording(camera_id, data)
            broadcast_frame(camera_id, data)
        else:
            print(f"[{camera_id}] Status received: {data}")

    print(f"Camera {camera_id} disconnected")


@sock.route("/ws/live/<camera_id>")
def live(ws, camera_id):
    check_name(camera_id)
    with state_lock:
        live_clients.setdefault(camera_id, set()).add(ws)
    print(f"Live viewer for {camera_id} connected")

    try:
        # Viewers never send anything; receive() just blocks
        # until the connection is closed.
        while ws.receive() is not None:
            pass
    except Exception:
        pass
    finally:
        with state_lock:
            live_clients[camera_id].discard(ws)
        print(f"Live viewer for {camera_id} disconnected")


def broadcast_frame(camera_id, data):
    with state_lock:
        clients = list(live_clients.get(camera_id, ()))

    for client in clients:
        try:
            client.send(data)
        except Exception:
            with state_lock:
                live_clients[camera_id].discard(client)


def save_frame_if_recording(camera_id, data):
    with state_lock:
        recording = recordings.get(camera_id)
        if recording is None:
            return
        recording["frame_number"] += 1
        frame_path = recording["dir"] / f"frame_{recording['frame_number']:06d}.jpg"

    frame_path.write_bytes(data)


@app.post("/api/cameras/<camera_id>/recording/start")
def start_recording(camera_id):
    check_name(camera_id)
    with state_lock:
        if camera_id in recordings:
            return jsonify(error="Recording already running"), 409

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        frames_dir = RECORDINGS_DIR / camera_id / timestamp
        frames_dir.mkdir(parents=True, exist_ok=True)
        recordings[camera_id] = {"dir": frames_dir, "frame_number": 0}

    return jsonify(status="recording")


@app.post("/api/cameras/<camera_id>/recording/stop")
def stop_recording(camera_id):
    check_name(camera_id)
    with state_lock:
        recording = recordings.pop(camera_id, None)

    if recording is None:
        return jsonify(error="No recording running"), 409

    if recording["frame_number"] == 0:
        shutil.rmtree(recording["dir"])
        return jsonify(error="No frames received, nothing saved"), 409

    try:
        video_path = create_video(recording["dir"])
    except (subprocess.CalledProcessError, FileNotFoundError):
        return jsonify(error="Video creation failed (is ffmpeg installed?)"), 500

    return jsonify(status="saved", video=video_path.name)


def create_video(frames_dir):
    video_path = frames_dir.parent / f"{frames_dir.name}.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-framerate", "5",
            "-i", str(frames_dir / "frame_%06d.jpg"),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            str(video_path),
        ],
        check=True,
    )
    shutil.rmtree(frames_dir)
    return video_path


@app.get("/api/cameras/<camera_id>/videos")
def list_videos(camera_id):
    check_name(camera_id)
    camera_dir = RECORDINGS_DIR / camera_id
    videos = sorted((v.name for v in camera_dir.glob("*.mp4")), reverse=True)
    return jsonify(videos=videos)


@app.get("/api/cameras/<camera_id>/videos/<video_name>")
def get_video(camera_id, video_name):
    check_name(camera_id)
    if not re.fullmatch(r"[A-Za-z0-9_-]+\.mp4", video_name):
        abort(400)

    video_path = RECORDINGS_DIR / camera_id / video_name
    if not video_path.is_file():
        abort(404)
    return send_file(video_path)


if __name__ == "__main__":
    app.run(port=5000, debug=True)
