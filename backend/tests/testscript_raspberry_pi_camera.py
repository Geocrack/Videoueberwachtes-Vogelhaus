import asyncio
import io
import itertools

import websockets
from PIL import Image, ImageDraw

BACKEND_URL = "ws://localhost:5000/ws/camera/"
# BACKEND_URL = "wss://vogelhaus.simgut.me/ws/camera/vogelhaus-0"

def make_frame(n, color):
    img = Image.new("RGB", (320, 240), "darkgreen")
    draw = ImageDraw.Draw(img)
    x = (n * 10) % 280
    draw.rectangle([x, 100, x + 40, 140], fill=color)
    draw.text((10, 10), f"Frame {n}", fill="white")
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=100)
    return buf.getvalue()

async def start_camera_stream( name, color):
    async with websockets.connect(BACKEND_URL + name) as ws:
        print(f"Verbunden mit {BACKEND_URL}")
        for n in itertools.count():
            await ws.send(make_frame(n, color))
            await asyncio.sleep(0.5)


async def main():
    await asyncio.gather(
        start_camera_stream( "vogelhaus-0", "yellow"),
        start_camera_stream( "vogelhaus-1", "blue"),
        start_camera_stream( "vogelhaus-2", "cyan"),
    )



if __name__ == "__main__":
    asyncio.run(main())
