import threading
from pathlib import Path
from flask import Flask, jsonify, send_file
from flask_sock import Sock

app = Flask(__name__)
sock = Sock(app)

INDEX_HTML = Path(__file__).resolve().parent.parent / "index.html"

live_clients = set()
live_clients_lock = threading.Lock()


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.get("/")
def index():
    return send_file(INDEX_HTML)


@sock.route("/ws/camera")
def camera(ws):
    print("Kamera verbunden")
    while True:
        data = ws.receive()
        if data is None:
            break

        if isinstance(data, bytes):
            broadcast_frame(data)
        else:
            print(f"Status empfangen: {data}")

    print("Kamera getrennt")


@sock.route("/ws/live")
def live(ws):
    with live_clients_lock:
        live_clients.add(ws)
    print(f"Live-Client verbunden ({len(live_clients)} aktiv)")

    try:
        # Der Client schickt nie etwas; receive() dient nur dazu, blockierend auf die Trennung der Verbindung zu warten.
        while ws.receive() is not None:
            pass
    except Exception:
        pass
    finally:
        with live_clients_lock:
            live_clients.discard(ws)
        print(f"Live-Client getrennt ({len(live_clients)} aktiv)")


def broadcast_frame(data):
    with live_clients_lock:
        clients = list(live_clients)

    for client in clients:
        try:
            client.send(data)
        except Exception:
            with live_clients_lock:
                live_clients.discard(client)


if __name__ == "__main__":
    app.run(port=5000, debug=True)
