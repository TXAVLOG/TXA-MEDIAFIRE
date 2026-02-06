<p align="center">
  <img src="assets/logo.png" width="200" alt="TXA-M Logo">
</p>

# TXA MediaFire Bulk Downloader

**A modern, high-speed, and cross-platform CLI tool for downloading files and folders from MediaFire.**

![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS%20%7C%20Android-blue?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.10%20--%203.14-yellow?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![PyPI](https://img.shields.io/pypi/v/txa-m?style=flat-square)

## 🚀 Key Features

*   **Bulk Downloading**: Recursively download entire folders or single files.
*   **Smart Extraction**: Handles dynamic links using HTML parsing and Regex fallback.
*   **Multi-threaded**: Blazing fast downloads with configurable threading.
*   **Resumable**: Automatically skips files that already exist (hash check).
*   **Cross-Platform**: Optimized for **Windows**, **Linux**, **macOS**, and **Android (Termux)**.
*   **Beautiful UI**: Rich terminal interface with progress bars, statistics, and themes.
*   **Multi-language**: Built-in support for **English** and **Vietnamese**.

## 📥 Installation

```bash
pip install txa-m
```

> **Note**: Requires Python 3.10 or newer.

## 💻 Usage

Run the tool using the command `txa-m`.

**IMPORTANT**: Always wrap your **URLs** and **Paths** in double quotes (`"`)!

### 1. Basic Download
```bash
txa-m "https://www.mediafire.com/file/example.zip"
```

### 2. Download Folder to Specific Path
```bash
txa-m "https://www.mediafire.com/folder/example" -o "C:/MyDownloads"
```

### 3. Change Language 🇻🇳 / 🇺🇸
Switch between English and Vietnamese easily. The setting is saved globally.
```bash
# Switch to Vietnamese
txa-m --sl vi

# Switch to English
txa-m --sl en
```

### 4. Advanced Options
```bash
# 20 threads, ignore video files
txa-m "https://mediafire.com/..." -t 20 -ie ".mp4,.mkv"

# Check for updates
txa-m --u
```

## ⚙️ Command Options

| Option | Description |
| :--- | :--- |
| `mediafire_url` | The URL of the file or folder (Required for download). |
| `-o`, `--output` | Output directory (Supports `%USERPROFILE%`, `~`). |
| `-t`, `--threads` | Number of download threads (Default: 10). |
| `-u`, `--update` | Check for updates and auto-install via pip. |
| `--sl`, `--set-lang`| Set language (`en` or `vi`). |
| `-ie` | Ignore extensions (e.g. `.mp4,.mkv`). |
| `-in` | Ignore specific filenames. |
| `-v`, `--version` | Show version information. |
| `-h`, `--help` | Show the beautiful help menu. |

## 📱 Android (Termux) Guide

1.  Install **Termux** from F-Droid.
2.  Run the following commands:
    ```bash
    pkg update && pkg upgrade
    pkg install python
    pip install txa-m
    termux-setup-storage
    ```
3.  Download file to your internal storage:
    ```bash
    txa-m "LINK" -o "/sdcard/Download"
    ```

## 📜 Copyright

Copyright © 2026 TXA.
_This tool is for educational purposes only._
