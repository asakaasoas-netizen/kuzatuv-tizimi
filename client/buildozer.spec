[app]

title = System Sync
package.name = systemsync
package.domain = com.android.sys

source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0

requirements = python3,kivy,websockets,aiohttp,certifi

# Ruxsatlar
android.permissions = INTERNET, CAMERA, WAKE_LOCK, RECORD_AUDIO, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE

# Foreground service olib tashlandi - oddiy ilova sifatida ishlaydi
android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21
android.accept_sdk_license = True
android.archs = arm64-v8a, armeabi-v7a

[buildozer]
log_level = 2
warn_on_root = 1
