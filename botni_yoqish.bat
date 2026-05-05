@echo off
title Kuzatuv Boti - Server
color 0b

echo Kerakli kutubxonalar yuklanmoqda... (Biroz kuting)
pip install -r requirements.txt

echo.
echo ========================================================
echo        BOT VA SERVER MUVAFFAQIYATLI ISHGA TUSHDI!
echo ========================================================
echo.
echo Endi Telegramga kirib botingizga /start deb yozishingiz mumkin.
echo.
echo [Diqqat] Bot ishlashi uchun shu qora darcha ochiq turishi shart!
echo Yopib yuborsangiz bot ishlashdan to'xtaydi.
echo.

python main.py
pause
