@echo off
:: Administrator huquqini avtomatik so'rash
net session >nul 2>&1
if %errorLevel% neq 0 (
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit
)

echo Firewall vaqtincha o'chirilmoqda (test uchun)...
netsh advfirewall set allprofiles state off

echo.
echo ================================
echo Firewall O'CHIRILDI (test rejimi)
echo Telefon brauzerida sinab ko'ring:
echo http://192.168.0.111:8000
echo ================================
pause

echo Firewall qayta yoqilmoqda...
netsh advfirewall set allprofiles state on
netsh advfirewall firewall add rule name="FastAPI 8000" dir=in action=allow protocol=TCP localport=8000 profile=any
echo Firewall yoqildi va 8000 port ochiq qoldi!
pause
