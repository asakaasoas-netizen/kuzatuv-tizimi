[app]

title = System Sync
package.name = systemsync
package.domain = com.android.sys

source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.2

requirements = python3,kivy,websockets

android.permissions = INTERNET, WAKE_LOCK

android.api = 33
android.minapi = 21
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a

[buildozer]
log_level = 2
warn_on_root = 1
