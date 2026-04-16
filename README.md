# 🎬 FrameForge AI

FrameForge is a lightweight desktop video processing tool built with Python, PyQt6, OpenCV, and FFmpeg.  
It allows users to apply real-time motion blur effects and export high-quality rendered videos with customizable settings.

---

## ✨ Features

- 🎥 Real-time video preview
- 🌫️ Adjustable motion blur intensity (0–100)
- ⚡ High-speed video rendering using FFmpeg
- 🎯 Custom FPS output (60 / 90 / 120 / 240 / 360)
- 🖥️ Clean dark UI built with PyQt6
- 📦 Portable design (can be packaged into EXE)

---

## 📷 Preview

> ![Image Alt](https://github.com/EnukaSathmina/FrameForge/blob/7072a076b2f5109dd4c1f5ad6f4ddb1d54dd9971/img.png)

---
# 🚀 Download (Portable Version)

👉 [Download FrameForge](https://github.com/EnukaSathmina/FrameForge/releases/download/v1.0/FrameForge.exe)

📦 [View Release Notes](https://github.com/enukasathmina/FrameForge/releases/tag/v1.0):

### ▶️ How to use

1. Download `FrameForge.exe`
2. Double-click to open
3. Import video
4. Adjust motion blur & FPS
5. Click **Render**

✅ No installation required  

⚠️ Make sure FFmpeg is bundled (or included in release)

---

# 🧑‍💻 Run from Source Code

## 📦 Requirements

Install dependencies:

```bash
pip install opencv-python numpy PyQt6
```
Install FFmpeg:
```bash
https://www.gyan.dev/ffmpeg/builds/
```

Add FFmpeg to system PATH

### ▶️ Run
```bash
python FrameForgeAI.py
```

📁 Project Structure
FrameForge/<br>
│── FrameForgeAI.py<br>
│── icon.ico<br>
│── screenshot.png<br>
│── README.md

⚙️ Build EXE (Optional)
```bash
pyinstaller --onefile --windowed --icon=icon.ico FrameForgeAI.py
```

⚠️ Notes
- Rendering uses FFmpeg
- High FPS + blur = higher CPU usage
- Preview is optimized but not GPU accelerated

<h2 align="center">👨‍💻 Author</h2>

<p align="center">
  Made by <b>Enuka Sathmina</b>
</p>
