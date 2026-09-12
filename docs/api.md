# API des Backends

Das Backend spricht HTTP für alles, was die Oberfläche steuert, und WebSockets für die Bilder. Die Antworten sind JSON, außer bei Bildern und Videos. `<id>` ist die Kamera-ID, `<video>` der Dateiname einer Aufnahme ohne `.mp4`.

Unter Docker sind alle Pfade über nginx auf Port 8080 erreichbar, direkt am Backend auf Port 5000. Die Beispiele unten nutzen das Backend direkt.

## HTTP

| Methode  | Pfad                                    | Zweck                                                   |
|----------|-----------------------------------------|---------------------------------------------------------|
| `GET`    | `/health`                               | Healthcheck für Docker und Deployment                   |
| `GET`    | `/api/cameras`                          | Alle Kameras mit Status, Bildrate und Anzahl der Videos |
| `PUT`    | `/api/cameras/<id>/info`                | Name, Standort und Beschreibung setzen                  |
| `GET`    | `/api/cameras/<id>/poster.jpg`          | Letztes Standbild                                       |
| `POST`   | `/api/cameras/<id>/recording/start`     | Aufnahme starten, `409` läuft schon, `507` Platte voll  |
| `POST`   | `/api/cameras/<id>/recording/stop`      | Aufnahme beenden und als MP4 encodieren                 |
| `GET`    | `/api/cameras/<id>/videos`              | Aufnahmen mit Titel, Größe und Datum                    |
| `GET`    | `/api/cameras/<id>/videos/<video>.mp4`  | Video abspielen oder herunterladen                      |
| `PUT`    | `/api/cameras/<id>/videos/<video>/name` | Video umbenennen                                        |
| `DELETE` | `/api/cameras/<id>/videos/<video>`      | Video löschen                                           |

Kamera-IDs und Videonamen dürfen nur `A-Z a-z 0-9 _ -` enthalten, andere Pfade beantwortet das Backend mit `404`.

Beispiel, Kamera benennen:

```bash
curl -X PUT http://localhost:5000/api/cameras/vogelhaus-0/info -H "Content-Type: application/json" -d "{\"name\":\"Garten\",\"location\":\"Apfelbaum\"}"
```

Beispiel, Aufnahme starten und beenden:

```bash
curl -X POST http://localhost:5000/api/cameras/vogelhaus-0/recording/start
```

```bash
curl -X POST http://localhost:5000/api/cameras/vogelhaus-0/recording/stop
```

## WebSockets

| Pfad               | Richtung          | Inhalt                                             |
|--------------------|-------------------|----------------------------------------------------|
| `/ws/camera/<id>`  | Kamera -> Backend | pro Nachricht ein vollständiges JPEG als Binärdaten |
| `/ws/live/<id>`    | Backend -> Browser | dieselben JPEGs, an jeden verbundenen Zuschauer    |

Eine Kamera meldet sich allein dadurch an, dass sie sich mit `/ws/camera/<id>` verbindet. Was das Backend von den Bildern erwartet, steht in der [README](../README.md#eigene-kamera-anschließen). Textnachrichten auf der Kameraverbindung werden nicht weitergereicht, sondern nur im Log des Backends ausgegeben. Das eignet sich für Debug-Ausgaben der Firmware.
