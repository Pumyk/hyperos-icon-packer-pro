# HyperOS Icon Packer Pro

Automate the HyperOS icon pack injection pipeline. Built with Kivy + Buildozer for Android.

## Features

- **8-screen pipeline**: Welcome, Pick APK, Extract, Rename, Resize, Mask, Build, Done
- **Auto-detect icon shapes**: Generate iconback/iconmask/iconupon assets
- **Binary XML decoding**: Decode Android binary appfilter.xml
- **Smart resizing**: Trim transparency, resize with LANCZOS
- **Dark theme UI**: Live color-coded logging with progress bars
- **Threaded processing**: All heavy operations on background threads

## Quick Start

### GitHub Actions (Recommended)
1. Push to `main` branch
2. Wait 15-20 minutes for build
3. Download APK from **Actions** tab

### Local Build
```bash
cd kivy_app
pip install buildozer cython kivy pillow
buildozer android debug
# APK: bin/hyperosiconpackerpro-debug.apk
```

## Pipeline Flow

```
APK Selection -> Extract -> Rename by Package -> Resize -> Generate Masks -> Build ZIP -> Download
```

## Configuration

- Target API: 33 (Android 13)
- Min API: 26 (Android 8)
- Permissions: READ/WRITE/MANAGE_EXTERNAL_STORAGE
- Package: com.tools.hyperosiconpackerpro

## Project Structure

```
kivy_app/
  main.py           # All 8 screens + pipeline logic
  buildozer.spec    # Android build configuration
.github/workflows/
  build-apk.yml     # GitHub Actions auto-build
```

## Install on Device

```bash
adb install -r bin/hyperosiconpackerpro-debug.apk
```
