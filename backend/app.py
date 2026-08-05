import json
import os
import shutil
import subprocess
import threading
from pathlib import Path
from datetime import datetime

from flask_sock import Sock
from werkzeug.routing import BaseConverter
from flask import Flask, abort, jsonify, request, send_file


class SafeNameConverter(BaseConverter):
    # Camera and video names may only contain simple characters, so URLs cannot escape the recordings folder
    regex = r"[A-Za-z0-9_-]+"


app = Flask(__name__)
app.url_map.converters["name"] = SafeNameConverter
sock = Sock(app)

RECORDINGS_DIR = Path(os.environ.get("RECORDINGS_DIR", Path(__file__).resolve().parent / "recordings"))

state_lock = threading.Lock()
live_clients = {}  # camera_id -> set of connected live viewer websockets
recordings = {}    # camera_id -> {"dir": folder of the running recording, "frame_number": int}


def camera_dir(camera_id):
    return RECORDINGS_DIR / camera_id


@app.get("/health")
def health():
    return jsonify(status="ok")


# Live streaming

@sock.route("/ws/camera/<name:camera_id>")
def camera(ws, camera_id):
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


@sock.route("/ws/live/<name:camera_id>")
def live(ws, camera_id):
    with state_lock:
        live_clients.setdefault(camera_id, set()).add(ws)

    try:
        # Viewers never send anything; receive() just blocks until the connection is closed.
        while ws.receive() is not None:
            pass
    except Exception:
        pass
    finally:
        with state_lock:
            live_clients[camera_id].discard(ws)


def broadcast_frame(camera_id, data):
    with state_lock:
        clients = list(live_clients.get(camera_id, ()))

    for client in clients:
        try:
            client.send(data)
        except Exception:
            with state_lock:
                live_clients[camera_id].discard(client)


# Recording

def save_frame_if_recording(camera_id, data):
    with state_lock:
        recording = recordings.get(camera_id)
        if recording is None:
            return
        recording["frame_number"] += 1
        frame_path = recording["dir"] / f"frame_{recording['frame_number']:06d}.jpg"

    frame_path.write_bytes(data)


@app.post("/api/cameras/<name:camera_id>/recording/start")
def start_recording(camera_id):
    with state_lock:
        if camera_id in recordings:
            return jsonify(error="Recording already running"), 409

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        frames_dir = camera_dir(camera_id) / timestamp
        frames_dir.mkdir(parents=True, exist_ok=True)
        recordings[camera_id] = {"dir": frames_dir, "frame_number": 0}

    return jsonify(status="recording")


@app.post("/api/cameras/<name:camera_id>/recording/stop")
def stop_recording(camera_id):
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


# Videos

@app.get("/api/cameras/<name:camera_id>/videos")
def list_videos(camera_id):
    videos = []
    for video_file in camera_dir(camera_id).glob("*.mp4"):
        videos.append(video_file.name)

    videos.sort(reverse=True)
    return jsonify(videos=videos)


@app.get("/api/cameras/<name:camera_id>/videos/<name:video_stem>.mp4")
def get_video(camera_id, video_stem):
    video_path = camera_dir(camera_id) / f"{video_stem}.mp4"
    if not video_path.is_file():
        abort(404)
    return send_file(video_path)


# Camera info

@app.get("/api/cameras")
def list_cameras():
    cameras = []
    for folder in sorted(RECORDINGS_DIR.glob("*/")):
        info_file = folder / "info.json"
        if info_file.is_file():
            info = json.loads(info_file.read_text(encoding="utf-8"))
        else:
            info = {}

        cameras.append({"id": folder.name, **info})

    return jsonify(cameras=cameras)


@app.put("/api/cameras/<name:camera_id>/info")
def save_camera_info(camera_id):
    info = request.get_json()
    folder = camera_dir(camera_id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    return jsonify(status="saved")


if __name__ == "__main__":
    app.run(port=5000, debug=True)
