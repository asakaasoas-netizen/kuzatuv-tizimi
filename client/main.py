import asyncio
import threading
from kivy.app import App
from kivy.uix.label import Label
from kivy.clock import Clock

WS_URL = "ws://192.168.0.111:8000/ws/device"

status = ["Ulanilmoqda..."]

async def ws_loop():
    while True:
        try:
            import websockets
            status[0] = f"Serverga ulanilmoqda...\n{WS_URL}"
            async with websockets.connect(WS_URL, ping_interval=20) as ws:
                status[0] = "✅ Ulandi!\nTelegram botdan buyruq bering."
                while True:
                    msg = await ws.recv()
                    status[0] = f"Buyruq: {msg}"
        except Exception as e:
            status[0] = f"❌ Xatolik:\n{str(e)[:80]}\n5 soniyadan so'ng qayta..."
            await asyncio.sleep(5)

def run_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(ws_loop())

class StealthApp(App):
    def build(self):
        self.label = Label(
            text="Ishga tushirilmoqda...",
            font_size='16sp',
            halign='center'
        )
        # Thread ishga tushirish
        t = threading.Thread(target=run_loop, daemon=True)
        t.start()
        # Har 1 soniyada ekranni yangilash
        Clock.schedule_interval(self.update_ui, 1)
        return self.label

    def update_ui(self, dt):
        self.label.text = status[0]

if __name__ == '__main__':
    StealthApp().run()
