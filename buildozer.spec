[app]
title = Rating Money Calculator
package.name = ratingmoneycalculator
package.domain = org.wiskyn
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0.0
requirements = python3,kivy,pyjnius
orientation = portrait
fullscreen = 0

# No CAMERA permission is needed by this implementation:
# it launches the installed Android camera app using an intent.
# The camera app itself owns its camera permission.
android.api = 35
android.minapi = 23
android.ndk = 27b
android.archs = arm64-v8a
android.accept_sdk_license = True
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1
