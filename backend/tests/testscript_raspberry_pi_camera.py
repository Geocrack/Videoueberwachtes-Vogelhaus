import asyncio
import io
import itertools

import websockets
from PIL import Image, ImageDraw

BACKEND_URL = "ws://localhost:5000/ws/camera"

def make_frame(n):
    img = Image.new("RGB", (320, 240), "darkgreen")
    draw = ImageDraw.Draw(img)
    x = (n * 10) % 280
    draw.rectangle([x, 100, x + 40, 140], fill="yellow")
    draw.text((10, 10), f"Frame {n}", fill="white")
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=100)
    return buf.getvalue()

async def main():
    async with websockets.connect(BACKEND_URL) as ws:
        print(f"Verbunden mit {BACKEND_URL}")
        for n in itertools.count():
            await ws.send(make_frame(n))
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
