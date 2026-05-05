@echo off
title Mahalliy Serverga Bog'lash
color 0e

echo Mahalliy IP manzil aniqlanmoqda va kodga yozilmoqda...
python -c "import socket, re; s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('8.8.8.8', 80)); ip=s.getsockname()[0]; s.close(); f=open('client/service.py', 'r'); c=f.read(); f.close(); c=re.sub(r'WS_URL = \".*\"', f'WS_URL = \"ws://{ip}:8000/ws/device\"', c); c=re.sub(r'UPLOAD_URL = \".*\"', f'UPLOAD_URL = \"http://{ip}:8000/upload\"', c); f=open('client/service.py', 'w'); f.write(c); f.close(); print('\n====================================\nSIZNING IP MANZILINGIZ: ' + ip + '\nservice.py fayliga muvaffaqiyatli kiritildi!\n====================================')"

echo.
echo Endi github_yuklash.bat orqali fayllarni GitHubga jo'nating.
pause
