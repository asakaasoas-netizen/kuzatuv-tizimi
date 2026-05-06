[app]

title = System Sync
package.name = systemsync
package.domain = com.android.sys

source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 2.0

requirements = python3,kivy,websockets,aiohttp,certifi,pyjnius,multidict,yarl

android.permissions = INTERNET, CAMERA, WAKE_LOCK, RECORD_AUDIO, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE

android.api = 33
android.minapi = 21
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a
android.allow_cleartext_traffic = True

[buildozer]
log_level = 2
warn_on_root = 1
