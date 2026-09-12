"""
Vogelhaus-Kamera: Arducam Mega 3MP am Raspberry Pi Pico 2 W

SICHERHEITSAUSSTIEG (zwei Wege)
  A) Beim Start: Pico einstecken, warten bis die LED langsam blinkt,
     DANN BOOTSEL druecken. Nicht beim Einstecken gedrueckt halten,
     sonst landet der Pico im ROM-Bootloader statt in MicroPython.
  B) Im laufenden Betrieb: BOOTSEL etwa zwei Sekunden gedrueckt halten.
     Der Pico legt eine Markierungsdatei an und startet neu. Beim
     Hochfahren beendet er sich dann, bevor der Watchdog scharf wird.

  In beiden Faellen leuchtet die LED danach dauerhaft.
  Das ist noetig, weil ein einmal gestarteter Watchdog nicht mehr
  abschaltbar ist und die REPL sonst nach acht Sekunden wegbricht.

LED-MUSTER
  langsames Blinken (2x/s)   Startfenster, BOOTSEL bricht ab
  Dauerlicht                 Sicherheitsmodus, Skript beendet
  schnelles Blinken (5x/s)   WLAN-Verbindung wird aufgebaut
  aus, Blitz alle 2 s        Stream laeuft
  Doppelblitz pro Sekunde    Fehler, wartet auf neuen Versuch
  dauerhaft aus              Kamerastart oder TLS-Handshake

Voraussetzung: camera.py (Core-Electronics-Treiber) liegt auf dem Pico.

Verkabelung (Pico 2 W -> Arducam Mega):
  3V3 (Pin 36) -> VCC        GP18 (Pin 24) -> SCK
  GND (Pin 38) -> GND        GP19 (Pin 25) -> MOSI
  GP16 (Pin 21) -> MISO      GP17 (Pin 22) -> CS
"""

import network
import socket
import struct
import time
import gc
import os
import rp2
import machine
import binascii
import select
from machine import Pin, SPI
from camera import Camera


# ============================ Konfiguration ============================

WLAN_SSID = ""
WLAN_PASSWORT = ""

WS_URL = "wss://vogelhaus.simgut.me/ws/camera/vogelhaus-0"
GERAETENAME = "vogelhaus-0"

AUFLOESUNG = "320x240"
WEISSABGLEICH = "auto"
JPEG_QUALITAET = "mittel"     # hoch | mittel | niedrig

# Feste Bildrate, muss zur Encoding-Rate des Backends passen.
# 200 = 5 fps, 125 = 8 fps, 100 = 10 fps
INTERVALL_MS = 100

DEBUG = False
LED_STATUS = True
STARTVERZOEGERUNG_S = 5

WATCHDOG = True
NEUSTART_NACH_FEHLERN = 8

# BOOTSEL-Abfrage waehrend des Streams. Der Aufruf greift kurz auf die
# Flash-Chipselect-Leitung zu, deshalb nicht in jedem Durchlauf.
BOOTSEL_IM_BETRIEB = True
BOOTSEL_PRUEFUNG_ALLE = 10    # Frames, bei 10 fps also einmal pro Sekunde
SICHER_FLAG = "safe_mode.flag"

HERZSCHLAG_FRAMES = 20        # Blitz alle 20 Frames

PUFFER_BYTES = 60000
BLOCK_BYTES = 1024
SPI_TAKT = 8_000_000
PIN_SCK, PIN_MISO, PIN_MOSI, PIN_CS = 18, 16, 19, 17

MASKE_ZUFAELLIG = False
KOPF_RESERVE = 14
_QUALITAETSWERTE = {"hoch": 0, "mittel": 1, "niedrig": 2}


# ============================ Hilfsmittel ============================

_wdt = None
_led = None


class BootselAbbruch(Exception):
    """Wird geworfen, wenn BOOTSEL im Betrieb gedrueckt wurde."""


def wd():
    if _wdt:
        _wdt.feed()


def melde(*teile):
    if DEBUG:
        print(*teile)


def bootsel_gedrueckt():
    try:
        return rp2.bootsel_button() == 1
    except Exception:
        return False


def flag_vorhanden():
    try:
        os.stat(SICHER_FLAG)
        return True
    except OSError:
        return False


def flag_setzen():
    try:
        with open(SICHER_FLAG, "w") as f:
            f.write("1")
        return True
    except OSError as e:
        melde("Markierung konnte nicht geschrieben werden:", e)
        return False


def flag_loeschen():
    try:
        os.remove(SICHER_FLAG)
    except OSError:
        pass


_WARTEMUSTER = (1, 0, 1, 0, 0, 0, 0, 0, 0, 0)   # Doppelblitz pro Sekunde


def warte(sekunden):
    """Wartet, fuettert den Watchdog und zeigt das Fehlermuster."""
    ende = time.ticks_add(time.ticks_ms(), int(sekunden * 1000))
    i = 0
    while time.ticks_diff(ende, time.ticks_ms()) > 0:
        wd()
        if _led:
            _led.value(_WARTEMUSTER[i % 10])
        i += 1
        time.sleep_ms(100)
    if _led:
        _led.off()


def sicherheitsmodus_anzeigen():
    """Kurzes Stroboskop, danach Dauerlicht."""
    if _led:
        for _ in range(24):
            _led.toggle()
            time.sleep_ms(40)
        _led.on()
    print()
    print("=" * 52)
    print("  SICHERHEITSMODUS")
    print("  Das Kameraskript wurde NICHT gestartet.")
    print("  LED leuchtet dauerhaft, kein Watchdog aktiv.")
    print("=" * 52)


def startfenster():
    """Wartet und laesst sich per BOOTSEL abbrechen. True = abbrechen.

    Abfrage alle 50 ms statt alle 250 ms, damit der Knopfdruck
    zuverlaessig erkannt wird.
    """
    for i in range(STARTVERZOEGERUNG_S * 20):
        if bootsel_gedrueckt():
            return True
        if _led and i % 5 == 0:
            _led.toggle()
        time.sleep_ms(50)
    if _led:
        _led.off()
    return False


# ============================ WebSocket ============================

def ws_url_zerlegen(url):
    if url.startswith("wss://"):
        tls, rest, port = True, url[6:], 443
    elif url.startswith("ws://"):
        tls, rest, port = False, url[5:], 80
    else:
        raise ValueError("URL muss mit ws:// oder wss:// beginnen")
    schraegstrich = rest.find("/")
    hostport = rest if schraegstrich < 0 else rest[:schraegstrich]
    pfad = "/" if schraegstrich < 0 else rest[schraegstrich:]
    if ":" in hostport:
        host, p = hostport.split(":", 1)
        port = int(p)
    else:
        host = hostport
    return tls, host, port, pfad


class WebSocket:
    """Minimaler WebSocket-Client (RFC 6455)."""

    def __init__(self, url):
        self.tls, self.host, self.port, self.pfad = ws_url_zerlegen(url)
        self.sock = None
        self.poller = None

    def verbinden(self):
        # Jeder dieser Schritte kann mehrere Sekunden dauern, deshalb
        # dazwischen fuettern. Ohne das laeuft der Watchdog ab, bevor
        # der TLS-Handshake fertig ist.
        wd()
        adresse = socket.getaddrinfo(self.host, self.port)[0][-1]

        wd()
        s = socket.socket()
        s.settimeout(5)
        try:
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass
        s.connect(adresse)

        wd()
        if self.tls:
            import ssl
            try:
                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                ctx.verify_mode = ssl.CERT_NONE
                s = ctx.wrap_socket(s, server_hostname=self.host)
            except AttributeError:
                s = ssl.wrap_socket(s, server_hostname=self.host)

        wd()
        schluessel = binascii.b2a_base64(os.urandom(16)).strip().decode()
        s.write((
                        "GET %s HTTP/1.1\r\n"
                        "Host: %s\r\n"
                        "Upgrade: websocket\r\n"
                        "Connection: Upgrade\r\n"
                        "Sec-WebSocket-Key: %s\r\n"
                        "Sec-WebSocket-Version: 13\r\n"
                        "\r\n" % (self.pfad, self.host, schluessel)
                ).encode())

        antwort = b""
        while b"\r\n\r\n" not in antwort:
            wd()
            teil = s.read(1)
            if not teil:
                raise OSError("Verbindung waehrend des Handshakes abgebrochen")
            antwort += teil
            if len(antwort) > 2048:
                raise OSError("Handshake-Antwort unplausibel lang")

        statuszeile = antwort.split(b"\r\n")[0]
        if b"101" not in statuszeile:
            raise OSError("Handshake abgelehnt: %s" % statuszeile.decode())

        self.sock = s
        self.poller = select.poll()
        self.poller.register(s, select.POLLIN)

    def bild_senden(self, sicht, n):
        """Nutzlast liegt in sicht[KOPF_RESERVE : KOPF_RESERVE + n].
        Kopf und Nutzlast gehen in einem einzigen write() raus."""
        if n < 126:
            kopf = bytes((0x82, 0x80 | n))
        elif n < 65536:
            kopf = bytes((0x82, 0x80 | 126, n >> 8, n & 0xFF))
        else:
            kopf = bytes((0x82, 0x80 | 127, 0, 0, 0, 0,
                          (n >> 24) & 0xFF, (n >> 16) & 0xFF,
                          (n >> 8) & 0xFF, n & 0xFF))

        if MASKE_ZUFAELLIG:
            maske = os.urandom(4)
            for i in range(n):
                sicht[KOPF_RESERVE + i] ^= maske[i & 3]
        else:
            maske = b"\x00\x00\x00\x00"

        start = KOPF_RESERVE - len(kopf) - 4
        sicht[start:start + len(kopf)] = kopf
        sicht[start + len(kopf):KOPF_RESERVE] = maske
        self.sock.write(sicht[start:KOPF_RESERVE + n])

    def text_senden(self, text):
        daten = text.encode()
        rahmen = bytearray((0x81, 0x80 | len(daten)))
        rahmen.extend(b"\x00\x00\x00\x00")
        rahmen.extend(daten)
        self.sock.write(rahmen)

    def eingang_verarbeiten(self):
        """Beantwortet Ping-Frames. Ohne das trennt der Server nach ca. 40 s."""
        while self.poller and self.poller.poll(0):
            kopf = self.sock.read(2)
            if not kopf or len(kopf) < 2:
                raise OSError("Verbindung vom Server geschlossen")
            opcode = kopf[0] & 0x0F
            laenge = kopf[1] & 0x7F
            if laenge == 126:
                laenge = struct.unpack(">H", self.sock.read(2))[0]
            elif laenge == 127:
                laenge = struct.unpack(">Q", self.sock.read(8))[0]
            nutzlast = self.sock.read(laenge) if laenge else b""
            if opcode == 0x9:
                rahmen = bytearray((0x8A, 0x80 | len(nutzlast)))
                rahmen.extend(b"\x00\x00\x00\x00")
                rahmen.extend(nutzlast)
                self.sock.write(rahmen)
            elif opcode == 0x8:
                raise OSError("Server hat die Verbindung beendet")

    def schliessen(self):
        try:
            self.sock.write(b"\x88\x80\x00\x00\x00\x00")
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass
        self.sock = None
        self.poller = None


# ============================ Kamera ============================

PUFFER = bytearray(PUFFER_BYTES)
SICHT = memoryview(PUFFER)
MAX_JPEG = PUFFER_BYTES - KOPF_RESERVE

_BURST_CMD = bytes((0x3C,))
_SCRATCH = bytearray(1)


def kamera_starten():
    spi = SPI(0,
              sck=Pin(PIN_SCK),
              miso=Pin(PIN_MISO),
              mosi=Pin(PIN_MOSI),
              baudrate=SPI_TAKT)
    cs = Pin(PIN_CS, Pin.OUT)
    cam = Camera(spi, cs)
    cam.resolution = AUFLOESUNG
    cam.set_white_balance(WEISSABGLEICH)
    cam._write_reg(cam.CAM_REG_IMAGE_QUALITY, _QUALITAETSWERTE[JPEG_QUALITAET])
    cam._wait_idle()
    cam._write_reg(cam.CAM_REG_EXPOSURE_CONTROL, cam.EXPOSURE_PLUS_1)
    cam._wait_idle()
    cam.set_contrast(cam.CONTRAST_MINUS_1)
    cam.capture_jpg()
    return cam


def aufnahme_ausloesen(cam):
    cam._clear_fifo_flag()
    cam._wait_idle()
    cam._start_capture()


def aufnahme_abholen(cam):
    """Wartet auf das Bild und liest es hinter den Kopfbereich des Puffers.
    Rueckgabe: Laenge des JPEG in Byte, oder 0."""
    frist = time.ticks_add(time.ticks_ms(), 3000)
    while cam._get_bit(cam.ARDUCHIP_TRIG, cam.CAP_DONE_MASK) == 0:
        if time.ticks_diff(frist, time.ticks_ms()) < 0:
            raise OSError("Kamera meldet kein fertiges Bild")
        time.sleep_ms(1)
    cam._wait_idle()
    laenge = cam._read_fifo_length()

    if laenge <= 0 or laenge > MAX_JPEG:
        return 0

    cam.cs.off()
    cam.spi_bus.write(_BURST_CMD)
    cam.spi_bus.readinto(_SCRATCH)
    pos = 0
    while pos < laenge:
        n = laenge - pos
        if n > BLOCK_BYTES:
            n = BLOCK_BYTES
        cam.spi_bus.readinto(SICHT[KOPF_RESERVE + pos:KOPF_RESERVE + pos + n])
        pos += n
    cam.cs.on()

    ende = KOPF_RESERVE + laenge
    if PUFFER[ende - 2] != 0xFF or PUFFER[ende - 1] != 0xD9:
        anfang = ende - 1024
        if anfang < KOPF_RESERVE:
            anfang = KOPF_RESERVE
        idx = bytes(SICHT[anfang:ende]).rfind(b"\xff\xd9")
        if idx >= 0:
            laenge = anfang + idx + 2 - KOPF_RESERVE
    return laenge


# ============================ WLAN ============================

def wlan_verbinden(neu=False):
    wlan = network.WLAN(network.STA_IF)
    if neu:
        wlan.active(False)
        warte(1)
    wlan.active(True)
    try:
        wlan.config(pm=0xa11140)
    except Exception:
        pass
    try:
        wlan.config(hostname=GERAETENAME)
    except Exception:
        pass
    if not wlan.isconnected():
        wlan.connect(WLAN_SSID, WLAN_PASSWORT)
        for _ in range(300):            # 30 s, LED blinkt schnell
            wd()
            if wlan.isconnected():
                break
            if _led:
                _led.toggle()
            time.sleep_ms(100)
    if _led:
        _led.off()
    if not wlan.isconnected():
        raise OSError("WLAN-Verbindung fehlgeschlagen")
    return wlan


# ============================ Hauptprogramm ============================

def main():
    global _wdt, _led

    _led = Pin("LED", Pin.OUT) if LED_STATUS else None

    # Weg B: Beim letzten Lauf wurde BOOTSEL im Betrieb gedrueckt.
    # Hier aussteigen, bevor der Watchdog scharf wird.
    if flag_vorhanden():
        flag_loeschen()
        sicherheitsmodus_anzeigen()
        return

    # Weg A: Startfenster, noch ohne Watchdog.
    if startfenster():
        sicherheitsmodus_anzeigen()
        return

    # Kamera zuerst, noch ohne Watchdog. Der Treiber hat in _wait_idle()
    # kein Timeout, ein Verkabelungsfehler wuerde sonst zu einer
    # Neustartschleife statt zu einer lesbaren Fehlermeldung fuehren.
    melde("Kamera wird initialisiert ...")
    cam = kamera_starten()
    melde("Kamera bereit:", cam.camera_idx, AUFLOESUNG, JPEG_QUALITAET)

    if WATCHDOG:
        from machine import WDT
        _wdt = WDT(timeout=8000)

    fehler_in_folge = 0

    while True:
        ws = None
        try:
            wlan = wlan_verbinden(neu=(fehler_in_folge >= 3))
            melde("WLAN:", wlan.ifconfig()[0])

            ws = WebSocket(WS_URL)
            ws.verbinden()
            ws.text_senden("%s, %s, %s, %d ms" %
                           (GERAETENAME, AUFLOESUNG, JPEG_QUALITAET, INTERVALL_MS))
            melde("WebSocket verbunden")

            naechster = time.ticks_ms()
            gesendet = 0
            takt = 0
            bootsel_zaehler = 0

            aufnahme_ausloesen(cam)

            while True:
                wd()

                laenge = aufnahme_abholen(cam)
                aufnahme_ausloesen(cam)

                # Ab hier bis zum Senden arbeitet die Kamera bereits.
                # Die Bereinigung liegt bewusst in diesem Fenster.
                gc.collect()

                if BOOTSEL_IM_BETRIEB:
                    bootsel_zaehler += 1
                    if bootsel_zaehler >= BOOTSEL_PRUEFUNG_ALLE:
                        bootsel_zaehler = 0
                        if bootsel_gedrueckt():
                            raise BootselAbbruch()

                if laenge:
                    ws.bild_senden(SICHT, laenge)
                    gesendet += 1
                    if gesendet == 25:
                        fehler_in_folge = 0
                        melde("Stream laeuft")

                ws.eingang_verarbeiten()

                # Herzschlag: kurzer Blitz statt Dauerlicht, damit man
                # eine laufende Schleife von einer eingefrorenen unterscheidet.
                if _led:
                    takt += 1
                    if takt == HERZSCHLAG_FRAMES:
                        _led.on()
                    elif takt > HERZSCHLAG_FRAMES:
                        _led.off()
                        takt = 0

                naechster = time.ticks_add(naechster, INTERVALL_MS)
                rest = time.ticks_diff(naechster, time.ticks_ms())
                if rest > 0:
                    time.sleep_ms(rest)
                else:
                    naechster = time.ticks_ms()

        except BootselAbbruch:
            if ws:
                ws.schliessen()
            melde("BOOTSEL erkannt, Neustart in den Sicherheitsmodus")
            if flag_setzen():
                time.sleep_ms(300)
                machine.reset()
            # Markierung liess sich nicht schreiben: hier bleibt nur,
            # normal weiterzulaufen, sonst greift der Watchdog.
            warte(2)

        except KeyboardInterrupt:
            if _led:
                _led.off()
            if ws:
                ws.schliessen()
            melde("Beendet")
            return

        except Exception as e:
            if _led:
                _led.off()
            if ws:
                ws.schliessen()
            ws = None
            gc.collect()
            fehler_in_folge += 1
            melde("Fehler %d: %r" % (fehler_in_folge, e))

            if fehler_in_folge == 2:
                melde("Kamera wird neu initialisiert")
                try:
                    cam = kamera_starten()
                except Exception as e2:
                    melde("Kamera-Neustart fehlgeschlagen:", repr(e2))

            if WATCHDOG and fehler_in_folge >= NEUSTART_NACH_FEHLERN:
                melde("Zu viele Fehler, Neustart")
                time.sleep(1)
                machine.reset()

            pause = 2 * fehler_in_folge
            if pause > 20:
                pause = 20
            warte(pause)


main()