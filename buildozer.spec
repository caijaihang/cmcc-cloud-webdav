[app]
title = CMCC Cloud WebDAV
package.name = cmccwebdav
package.domain = org.cmccwebdav
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,txt,json
version = 1.2.0
requirements = python3,requests,wsgidav,cheroot,Pillow,pystray
orientation = portrait
osx.python_version = 3
osx.kivy_version = 1.9.1
fullscreen = 0
android.api = 33
android.minapi = 21
android.sdk = 33
android.ndk = 25b
android.arch = arm64-v8a
android.permissions = INTERNET,ACCESS_NETWORK_STATE,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
[buildozer]
log_level = 2
warn_on_root = 1
