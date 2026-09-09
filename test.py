from machine import Pin, SPI
from camera import Camera
import time, os

spi = SPI(0, sck=Pin(18), miso=Pin(16), mosi=Pin(19), baudrate=8_000_000)
cs = Pin(17, Pin.OUT)

cam = Camera(spi, cs, debug_text_enabled=True)
print("Erkannte Kamera:", cam.camera_idx)

cam.resolution = '640x480'
cam.set_white_balance('home')

try:
    os.remove('bild.jpg')
except OSError:
    pass

cam.capture_jpg()
time.sleep_ms(50)
cam.save_jpg('bild.jpg')
print("Groesse:", os.stat('bild.jpg')[6], "Bytes")