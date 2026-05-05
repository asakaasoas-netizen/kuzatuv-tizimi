@echo off
title GitHubga Yuklash
color 0A

echo ===================================================
echo     Kuzatuv loyihasini GitHubga yuklash dasturi
echo ===================================================
echo.

IF NOT EXIST ".git" git init

git remote remove origin 2>nul
git remote add origin https://github.com/asakaasoas-netizen/kuzatuv-tizimi.git
git branch -M main

echo Fayllar saqlanmoqda...
git add .
git commit -m "Avtomatik saqlash: loyiha yangilandi"

echo.
echo GitHubga yuklanmoqda...
git push -u origin main

echo.
echo ====================================================
echo YUKLASH TUGADI! 
echo Agar yuqorida "error" yozuvi chiqmagan bo'lsa,
echo hamma fayllar muvaffaqiyatli yuklangan.
echo ====================================================
pause
