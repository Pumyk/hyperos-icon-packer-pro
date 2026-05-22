[app]

title = HyperOS Icon Packer Pro
package.name = hyperosiconpackerpro
package.domain = com.tools
source.dir = .
version = 1.0.0
requirements = python3,kivy,pillow,android
orientation = portrait
fullscreen = 0

android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,MANAGE_EXTERNAL_STORAGE
android.api = 33
android.minapi = 26
android.ndk = 25b
android.copy_libs = 1
android.archs = arm64-v8a,armeabi-v7a
android.enable_androidx = True

[buildozer]
log_level = 2
warn_on_root = 1
build_dir = .buildozer
bin_dir = ./bin
