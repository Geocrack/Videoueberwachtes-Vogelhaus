# Server einrichten

Diese Anleitung beschreibt, was auf einem frischen Server zu tun ist, damit das Vogelhaus dort läuft, von außen erreichbar ist und sich bei einem Push auf `main` selbst aktualisiert. Die Anwendung und ihre Umgebungsvariablen sind in der [README](../README.md) beschrieben, die API in [api.md](api.md).

Am Ende laufen auf dem Server drei Dinge:

1. der Anwendungsstack aus der `docker-compose.yml`, also nginx auf Port 8080 und das Backend
   auf Port 5000
2. ein self-hosted GitHub-Runner, der das Deployment ausführt
3. `cloudflared` für den Cloudflare Tunnel, über den der Stack unter der eigenen Domain
   erreichbar ist

Gebraucht wird ein Linux-Server. Dazu eine Domain, deren DNS bei Cloudflare liegt. Ein offener Port im Router ist nicht nötig.


## 1. Docker installieren

Docker aus dem offiziellen Docker-Repository installieren, damit das Compose-Plugin dabei ist. Der Deploy-Workflow ruft `docker compose` auf.

```bash
apt update && apt install -y ca-certificates curl git
```

```bash
install -m 0755 -d /etc/apt/keyrings && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
```

```bash
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
```

```bash
apt update && apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Läuft der Server als LXC-Container unter Proxmox, müssen in den Container-Optionen unter *Features* die Punkte `nesting` und `keyctl` aktiviert sein, sonst startet der Docker-Daemon nicht.


## 2. Benutzer für den Runner anlegen

Der GitHub-Runner bekommt einen eigenen Benutzer ohne Root-Rechte. Damit läuft alles, was der Workflow ausführt, getrennt vom Rest des Systems. Der Benutzer muss in der Gruppe `docker` sein, weil er die Images baut und den Stack startet.

```bash
adduser --disabled-password --gecos "" runner && usermod -aG docker runner
```


## 3. Stack zum ersten Mal starten

Als Benutzer `runner` das Repository klonen und den Stack bauen:

```bash
su - runner
```

```bash
git clone https://github.com/<owner>/Videoueberwachtes-Vogelhaus.git && cd Videoueberwachtes-Vogelhaus
```

```bash
docker compose up -d --build --wait
```

Der erste Build dauert einige Minuten. `--wait` kehrt erst zurück, wenn der Healthcheck des Backends grün ist. Prüfen:

```bash
curl http://localhost:8080/health
```

Die Antwort muss `{"status": "ok"}` sein. Die Oberfläche ist jetzt im lokalen Netz unter
`http://<ip-des-servers>:8080` erreichbar.

## 4. Konfiguration

Die Grenzwerte des Backends stehen in der `docker-compose.yml` unter `environment`. Änderungen gehören ins Repository, weil das nächste Deployment die Datei auf dem Server überschreibt.

Port 8080 ist der einzige Port, der von außen gebraucht wird. Port 5000 ist nur für den direkten Zugriff auf das Backend im lokalen Netz offen.


## 5. Cloudflare Tunnel

`cloudflared` läuft als Container auf dem Server, baut eine ausgehende Verbindung zu Cloudflare auf und reicht Anfragen an Port 8080 weiter. Cloudflare terminiert TLS, nginx im Container spricht nur HTTP. Es ist keine Portfreigabe und kein Zertifikat auf dem Server nötig.

Im Cloudflare-Dashboard unter *Zero Trust*, *Networks*, *Tunnels* einen Tunnel vom Typ *Cloudflared* anlegen. Cloudflare zeigt danach einen Token an. Damit den Container starten:

```bash
docker run -d --name cloudflared --restart unless-stopped cloudflare/cloudflared:latest tunnel --no-autoupdate run --token <token>
```

```bash
docker logs cloudflared
```

Im Log muss `Registered tunnel connection` stehen. Dann im Tunnel unter *Public Hostname* einen Eintrag anlegen:

| Feld      | Wert                    |
|-----------|-------------------------|
| Subdomain | `vogelhaus`             |
| Domain    | die eigene Domain       |
| Type      | `HTTP`                  |
| URL       | `<ip-des-servers>:8080` |

Als URL die IP des Servers im lokalen Netz eintragen. Die IP sollte im Router fest vergeben sein.

Cloudflare legt den DNS-Eintrag selbst an. WebSockets sind im Tunnel standardmäßig erlaubt. Danach ist die Oberfläche unter `https://vogelhaus.<domain>` erreichbar und die Kameras verbinden sich per `wss://vogelhaus.<domain>/ws/camera/<id>`.

Der Stack braucht nur irgendetwas, das `https` und `wss` auf Port 8080 weiterreicht und WebSocket-Upgrades durchlässt. Ein Reverse Proxy wie Caddy mit Let's Encrypt und Portfreigabe für 80 und 443 geht genauso. Der Proxy darf WebSocket-Verbindungen nicht vor 3600 Sekunden trennen, so lange hält nginx im Container sie.




## 6. Betrieb

Der Stack liegt nach dem ersten Deployment unter `/home/runner/actions-runner/_work/Videoueberwachtes-Vogelhaus/Videoueberwachtes-Vogelhaus`. Von dort aus funktionieren alle Befehle.

So kann man freien Platz prüfen:

```bash
df -h /var/lib/docker
```

Oder Aufnahmen sichern:

```bash
docker run --rm -v videoueberwachtes-vogelhaus_recordings:/data -v "$PWD":/backup alpine tar czf /backup/recordings.tgz -C /data .
```

Nach einem Neustart des Servers starten Docker, der Stack, `cloudflared` und der Runner von selbst. `cloudflared` wird aktualisiert, indem der Container entfernt und mit dem Befehl aus Abschnitt 5 neu gestartet wird. Der Runner aktualisiert sich selbst.
