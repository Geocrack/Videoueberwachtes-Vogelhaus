# Videoüberwachtes Vogelhaus

Kameras schicken JPEG-Frames per WebSocket ans Backend (Flask), das Frontend (React) zeigt sie live an und kann sie als MP4 aufnehmen.

## Lokal starten

### Mit Docker

```bash
docker compose up -d --build --wait   # baut Frontend + Backend, wartet bis healthy
docker compose logs -f backend        # Logs
docker compose down                   # stoppen (Volume mit Aufnahmen bleibt)
```

UI: <http://localhost:8080> · Backend direkt: <http://localhost:5000>

### Ohne Docker (Entwicklung, mit Hot Reload)

Voraussetzungen: Python 3.12, Node 24+, `ffmpeg` im PATH (nur für Aufnahmen nötig).

```bash
# Backend, Terminal 1
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py                         # http://localhost:5000

# Frontend, Terminal 2
cd frontend
npm install
npm run dev                           # http://localhost:5173
```

Der Vite-Devserver proxyt `/api` und `/ws` auf `localhost:5000` — die UI ist unter `http://localhost:5173` erreichbar.

### Testkamera ohne Hardware

```bash
cd backend
python tests/testscript_raspberry_pi_camera.py   # BACKEND_URL im Skript auf localhost stellen
```

Sendet drei Fake-Kameras (`vogelhaus-0/1/2`) mit generierten Frames.

## Kamera anschließen (Raspberry Pi Pico)

Eine WebSocket-Verbindung öffnen und darüber die Bilder senden:

```
ws://localhost:5000/ws/camera/<kamera-id>        # lokal, Backend direkt
ws://localhost:8080/ws/camera/<kamera-id>        # lokal, über nginx
wss://vogelhaus.simgut.me/ws/camera/<kamera-id>  # Produktion
```

* **`<kamera-id>`**: frei wählbar, nur `A-Z a-z 0-9 _ -` (z. B. `vogelhaus-0`). Die Kamera erscheint automatisch in der UI, es ist keine Registrierung nötig.
* **Format**: pro Frame **eine binäre WebSocket-Nachricht**, die genau eine vollständige JPEG-Datei enthält. Kein Base64, kein JSON, kein Header, keine Aufteilung über mehrere Nachrichten.
* **Textnachrichten** auf derselben Verbindung werden nur als Statusmeldung ins Log geschrieben — nützlich für Debug-Ausgaben.
* **Bildrate**: ca. **5 Frames/s** (alle 200 ms) senden. Aufnahmen werden mit 5 fps encodiert, bei anderer Rate laufen die MP4s zu schnell oder zu langsam.
* **Timeout**: mindestens ein Frame alle 15 s, sonst gilt die Kamera als offline.
* **Auflösung**: beliebig, wird aus dem ersten Frame übernommen (z. B. 320×240).


### Optionale Metadaten

```bash
curl -X PUT http://localhost:5000/api/cameras/vogelhaus-0/info \
  -H 'Content-Type: application/json' \
  -d '{"name":"Garten","location":"Apfelbaum","description":"Futterhaus am Stamm"}'
```

## Ports

| Port | Dienst                                        |
|------|-----------------------------------------------|
| 8080 | Frontend (nginx), proxyt `/api`, `/ws`, `/health` |
| 5000 | Backend (Flask/gunicorn)                      |
| 5173 | Vite-Devserver (nur ohne Docker)              |
