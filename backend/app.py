import json
import os
import shutil
import subprocess
import threading
import time
from collections import deque
from io import BytesIO
from pathlib import Path
from datetime import datetime

from PIL import Image
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

ONLINE_TIMEOUT_SECONDS = float(os.environ.get("ONLINE_TIMEOUT_SECONDS", 15))
STATE_WRITE_INTERVAL = float(os.environ.get("STATE_WRITE_INTERVAL", 30))
POSTER_WRITE_INTERVAL = float(os.environ.get("POSTER_WRITE_INTERVAL", 60))
FPS_WINDOW = 20
MAX_TITLE_LENGTH = 120
MAX_RECORDING_SECONDS = float(os.environ.get("MAX_RECORDING_SECONDS", 1800))
MAX_RECORDING_FRAMES = int(os.environ.get("MAX_RECORDING_FRAMES", 20000))
MIN_FREE_DISK_MB = float(os.environ.get("MIN_FREE_DISK_MB", 2000))
WATCHDOG_INTERVAL = float(os.environ.get("WATCHDOG_INTERVAL", 10))

state_lock = threading.Lock()
names_lock = threading.Lock()
live_clients = {}  # camera_id -> set of connected live viewer websockets
recordings = {}    # camera_id -> {"dir": folder of the running recording, "frame_number": int}
camera_state = {}  # camera_id -> live connection state, see note_camera_connected()


def camera_dir(camera_id):
    return RECORDINGS_DIR / camera_id


def write_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.{threading.get_ident()}.tmp")
    tmp_path.write_bytes(data)
    os.replace(tmp_path, path)


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def free_disk_mb():
    path = RECORDINGS_DIR if RECORDINGS_DIR.is_dir() else RECORDINGS_DIR.parent
    try:
        return shutil.disk_usage(path).free / (1024 * 1024)
    except OSError:
        return float("inf")


@app.get("/health")
def health():
    return jsonify(status="ok")


# Live streaming

@sock.route("/ws/camera/<name:camera_id>")
def camera(ws, camera_id):
    print(f"Camera {camera_id} connected")
    note_camera_connected(camera_id)
    last_frame = None
    try:
        while True:
            data = ws.receive()
            if data is None:
                break

            if isinstance(data, bytes):
                data = rotate_frame(data)
                last_frame = data
                note_frame(camera_id, data)
                save_frame_if_recording(camera_id, data)
                broadcast_frame(camera_id, data)
            else:
                print(f"[{camera_id}] Status received: {data}")
    finally:
        note_camera_disconnected(camera_id, last_frame)
        print(f"Camera {camera_id} disconnected")


@sock.route("/ws/live/<name:camera_id>")
def live(ws, camera_id):
    with state_lock:
        live_clients.setdefault(camera_id, set()).add(ws)

    try:
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

def read_stored_state(camera_id):
    state_file = camera_dir(camera_id) / "state.json"
    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def note_camera_connected(camera_id):
    stored = read_stored_state(camera_id)

    with state_lock:
        state = camera_state.get(camera_id)
        if state is None:
            state = {
                "connections": 0,
                "last_frame_at": None,
                "frame_times": deque(maxlen=FPS_WINDOW),
                "last_seen": stored.get("last_seen"),
                "width": stored.get("width"),
                "height": stored.get("height"),
                "state_written_at": 0.0,
                "poster_written_at": 0.0,
            }
            camera_state[camera_id] = state

        state["connections"] += 1


def note_frame(camera_id, data):
    now = time.time()
    timestamp = now_iso()

    with state_lock:
        state = camera_state.get(camera_id)
        if state is None:
            return

        state["last_frame_at"] = now
        state["frame_times"].append(now)
        state["last_seen"] = timestamp

        needs_size = state["width"] is None
        write_state = now - state["state_written_at"] >= STATE_WRITE_INTERVAL
        write_poster = now - state["poster_written_at"] >= POSTER_WRITE_INTERVAL
        if write_state:
            state["state_written_at"] = now
        if write_poster:
            state["poster_written_at"] = now

    if needs_size:
        store_frame_size(camera_id, data)
    if write_state:
        persist_camera_state(camera_id)
    if write_poster:
        save_poster(camera_id, data)


def save_poster(camera_id, data):
    try:
        write_atomic(camera_dir(camera_id) / "poster.jpg", data)
    except OSError as error:
        print(f"[{camera_id}] Could not save poster: {error}")


def store_frame_size(camera_id, data):
    try:
        width, height = Image.open(BytesIO(data)).size
    except (OSError, ValueError):
        return

    with state_lock:
        state = camera_state.get(camera_id)
        if state is not None:
            state["width"] = width
            state["height"] = height

def rotate_frame(data):
    try:
        image = Image.open(BytesIO(data))
        buffer = BytesIO()
        image.transpose(Image.Transpose.ROTATE_180).save(buffer, format="JPEG", quality=85)
        return buffer.getvalue()
    except (OSError, ValueError):
        return data


def persist_camera_state(camera_id):
    with state_lock:
        state = camera_state.get(camera_id)
        if state is None or state["last_seen"] is None:
            return

        stored = {
            "last_seen": state["last_seen"],
            "width": state["width"],
            "height": state["height"],
        }

    try:
        write_atomic(camera_dir(camera_id) / "state.json", json.dumps(stored, indent=2).encode("utf-8"))
    except OSError as error:
        print(f"[{camera_id}] Could not save state: {error}")


def note_camera_disconnected(camera_id, last_frame=None):
    with state_lock:
        state = camera_state.get(camera_id)
        if state is None:
            return

        state["connections"] = max(0, state["connections"] - 1)
        if state["connections"] > 0:
            return

        state["frame_times"].clear()
        has_frames = state["last_seen"] is not None

    persist_camera_state(camera_id)
    if last_frame is not None and has_frames:
        save_poster(camera_id, last_frame)


def measure_fps(frame_times):
    if len(frame_times) < 2:
        return None

    span = frame_times[-1] - frame_times[0]
    if span <= 0:
        return None

    return round((len(frame_times) - 1) / span, 1)


def camera_snapshot(camera_id):
    now = time.time()

    with state_lock:
        state = camera_state.get(camera_id)
        recording = camera_id in recordings

        if state is None:
            connected, last_frame_at, frame_times, history = False, None, [], None
        else:
            connected = state["connections"] > 0
            last_frame_at = state["last_frame_at"]
            frame_times = list(state["frame_times"])
            history = {
                "last_seen": state["last_seen"],
                "width": state["width"],
                "height": state["height"],
            }

    if history is None:
        stored = read_stored_state(camera_id)
        history = {
            "last_seen": stored.get("last_seen"),
            "width": stored.get("width"),
            "height": stored.get("height"),
        }

    online = (
        connected
        and last_frame_at is not None
        and now - last_frame_at < ONLINE_TIMEOUT_SECONDS
    )

    return {
        **history,
        "online": online,
        "recording": recording,
        "fps": measure_fps(frame_times) if online else None,
    }


# Recording

class RecordingError(Exception):
    def __init__(self, message, status):
        super().__init__(message)
        self.status = status


def save_frame_if_recording(camera_id, data):
    with state_lock:
        recording = recordings.get(camera_id)
        if recording is None:
            return
        recording["frame_number"] += 1
        frame_path = recording["dir"] / f"frame_{recording['frame_number']:06d}.jpg"

    try:
        frame_path.write_bytes(data)
    except OSError as error:
        with state_lock:
            current = recordings.get(camera_id)
            if current is recording:
                current["frame_number"] -= 1
        print(f"[{camera_id}] Could not save frame: {error}")


def finish_recording(camera_id):
    with state_lock:
        recording = recordings.pop(camera_id, None)

    if recording is None:
        raise RecordingError("No recording running", 409)

    if recording["frame_number"] == 0:
        shutil.rmtree(recording["dir"], ignore_errors=True)
        raise RecordingError("No frames received, nothing saved", 409)

    try:
        return create_video(recording["dir"])
    except FileNotFoundError:
        raise RecordingError("Video creation failed (is ffmpeg installed?)", 500)
    except subprocess.CalledProcessError as error:
        details = error.stderr.decode("utf-8", "replace").strip()
        print(f"[{camera_id}] ffmpeg failed: {details}")
        raise RecordingError(
            f"Video creation failed: {details.splitlines()[-1] if details else 'unknown error'}", 500
        )


@app.post("/api/cameras/<name:camera_id>/recording/start")
def start_recording(camera_id):
    if free_disk_mb() < MIN_FREE_DISK_MB:
        return jsonify(error="Not enough free disk space to start a recording"), 507

    with state_lock:
        if camera_id in recordings:
            return jsonify(error="Recording already running"), 409

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        frames_dir = camera_dir(camera_id) / timestamp
        frames_dir.mkdir(parents=True, exist_ok=True)
        recordings[camera_id] = {
            "dir": frames_dir,
            "frame_number": 0,
            "started_at": time.time(),
        }

    return jsonify(status="recording")


@app.post("/api/cameras/<name:camera_id>/recording/stop")
def stop_recording(camera_id):
    title = requested_title()

    try:
        video_path = finish_recording(camera_id)
    except RecordingError as error:
        return jsonify(error=str(error)), error.status

    store_video_name(camera_id, video_path.name, title)
    return jsonify(status="saved", video=video_path.name, name=title)


def overdue_recordings():
    now = time.time()
    low_on_disk = free_disk_mb() < MIN_FREE_DISK_MB
    overdue = []

    with state_lock:
        for camera_id, recording in recordings.items():
            if now - recording["started_at"] >= MAX_RECORDING_SECONDS:
                overdue.append((camera_id, "time limit reached"))
            elif recording["frame_number"] >= MAX_RECORDING_FRAMES:
                overdue.append((camera_id, "frame limit reached"))
            elif low_on_disk:
                overdue.append((camera_id, "free disk space is running out"))

    return overdue


def stop_overdue_recordings():
    for camera_id, reason in overdue_recordings():
        print(f"[{camera_id}] Stopping recording automatically: {reason}")
        try:
            video_path = finish_recording(camera_id)
            print(f"[{camera_id}] Saved {video_path.name}")
        except RecordingError as error:
            print(f"[{camera_id}] Automatic stop failed: {error}")


def recover_interrupted_recordings():
    for frames_dir in sorted(RECORDINGS_DIR.glob("*/*/")):
        if not frames_dir.is_dir():
            continue

        if not any(frames_dir.glob("frame_*.jpg")):
            shutil.rmtree(frames_dir, ignore_errors=True)
            continue

        print(f"Recovering interrupted recording {frames_dir}")
        try:
            video_path = create_video(frames_dir)
            print(f"Recovered {video_path.name}")
        except (subprocess.CalledProcessError, FileNotFoundError, OSError) as error:
            print(f"Could not recover {frames_dir}: {error}")


def recording_watchdog():
    recover_interrupted_recordings()

    while True:
        time.sleep(WATCHDOG_INTERVAL)
        try:
            stop_overdue_recordings()
        except Exception as error:
            print(f"Recording watchdog error: {error}")


def create_video(frames_dir):
    video_path = frames_dir.parent / f"{frames_dir.name}.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-nostdin",
            "-loglevel", "error",
            "-framerate", "10",
            "-i", str(frames_dir / "frame_%06d.jpg"),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            str(video_path),
        ],
        check=True,
        capture_output=True,
    )
    shutil.rmtree(frames_dir)
    return video_path


# Videos

def video_names_file(camera_id):
    return camera_dir(camera_id) / "video_names.json"


def read_video_names(camera_id):
    try:
        names = json.loads(video_names_file(camera_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}

    return names if isinstance(names, dict) else {}


def store_video_name(camera_id, video_name, title):
    with names_lock:
        names = read_video_names(camera_id)
        if title:
            names[video_name] = title
        else:
            names.pop(video_name, None)

        write_atomic(video_names_file(camera_id), json.dumps(names, indent=2).encode("utf-8"))


def requested_title():
    payload = request.get_json(silent=True) or {}
    return str(payload.get("name", "")).strip()[:MAX_TITLE_LENGTH]


def video_entry(video_file, names):
    try:
        created = datetime.strptime(video_file.stem, "%Y-%m-%d_%H-%M-%S")
    except ValueError:
        created = datetime.fromtimestamp(video_file.stat().st_mtime)

    return {
        "name": video_file.name,
        "title": names.get(video_file.name, ""),
        "size": video_file.stat().st_size,
        "created": created.astimezone().isoformat(timespec="seconds"),
    }


@app.get("/api/cameras/<name:camera_id>/videos")
def list_videos(camera_id):
    names = read_video_names(camera_id)
    videos = [video_entry(video_file, names) for video_file in camera_dir(camera_id).glob("*.mp4")]
    videos.sort(key=lambda video: video["name"], reverse=True)
    return jsonify(videos=videos)


@app.put("/api/cameras/<name:camera_id>/videos/<name:video_stem>/name")
def rename_video(camera_id, video_stem):
    video_path = camera_dir(camera_id) / f"{video_stem}.mp4"
    if not video_path.is_file():
        abort(404)

    title = requested_title()
    store_video_name(camera_id, video_path.name, title)
    return jsonify(status="saved", name=title)


@app.delete("/api/cameras/<name:camera_id>/videos/<name:video_stem>")
def delete_video(camera_id, video_stem):
    video_path = camera_dir(camera_id) / f"{video_stem}.mp4"
    if not video_path.is_file():
        abort(404)

    video_path.unlink()
    store_video_name(camera_id, video_path.name, "")
    return jsonify(status="deleted")


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
            try:
                info = json.loads(info_file.read_text(encoding="utf-8"))
            except ValueError:
                info = {}
        else:
            info = {}

        cameras.append({
            **info,
            **camera_snapshot(folder.name),
            "id": folder.name,
            "video_count": len(list(folder.glob("*.mp4"))),
            "has_poster": (folder / "poster.jpg").is_file(),
        })

    listed = {camera["id"] for camera in cameras}
    with state_lock:
        unlisted = [camera_id for camera_id in camera_state if camera_id not in listed]

    for camera_id in unlisted:
        cameras.append({
            **camera_snapshot(camera_id),
            "id": camera_id,
            "video_count": 0,
            "has_poster": False,
        })

    cameras.sort(key=lambda camera: camera["id"])
    cameras.sort(key=lambda camera: camera["last_seen"] or "", reverse=True)
    cameras.sort(key=lambda camera: not camera["online"])

    return jsonify(cameras=cameras)


@app.get("/api/cameras/<name:camera_id>/poster.jpg")
def get_poster(camera_id):
    poster_path = camera_dir(camera_id) / "poster.jpg"
    if not poster_path.is_file():
        abort(404)

    response = send_file(poster_path, mimetype="image/jpeg")
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.put("/api/cameras/<name:camera_id>/info")
def save_camera_info(camera_id):
    info = request.get_json()
    folder = camera_dir(camera_id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    return jsonify(status="saved")


threading.Thread(target=recording_watchdog, name="recording-watchdog", daemon=True).start()


if __name__ == "__main__":
    app.run(port=5000, debug=True)
