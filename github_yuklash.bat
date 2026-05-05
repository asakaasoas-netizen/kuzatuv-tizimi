@echo off
title GitHubga Yuklash
color 0A

echo ===================================================
echo     Kuzatuv loyihasini GitHubga yuklash dasturi
echo ===================================================
echo.

IF EXIST ".git" goto do_push

:do_init
echo [Diqqat] Siz birinchi marta yuklayapsiz, sozlamalar qilinmoqda...
git init
git remote add origin https://github.com/asakaasoas-netizen/kuzatuv-tizimi.git
git branch -M main

:do_push
echo.
echo Fayllar saqlanmoqda...
git add .
git commit -m "Avtomatik saqlash: loyiha yangilandi"

echo.
echo GitHubga yuklanmoqda...
git push -u origin main

echo.
echo ====================================================
echo MUVAFFAQIYATLI YUKLANDI! 
echo Endi GitHubdagi "Actions" bo'limiga kirib APK tayyor 
echo bo'lishini kuzatishingiz mumkin.
echo ====================================================
pause
