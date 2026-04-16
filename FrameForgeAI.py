import sys
import os
import subprocess
import cv2
import re
import numpy as np
import ctypes

# Display Fixes for High DPI screens
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
os.environ["QT_QPA_PLATFORM"] = "windows"

from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QFont, QIcon

def resource_path(path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, path)

def load_icon():
    icon_path = resource_path("icon.ico")
    icon = QIcon(icon_path)
    if icon.isNull():
        return QIcon()  # Returns empty icon if file missing
    return icon

DARK_STYLE = """
QMainWindow { background-color: #121212; }
QLabel { color: #E0E0E0; font-family: 'Segoe UI'; }
QPushButton {
    background-color: #2D2D2D; color: white; border-radius: 6px;
    padding: 10px 20px; font-weight: bold; border: 1px solid #3D3D3D;
}
QPushButton:hover { background-color: #3D3D3D; border-color: #0078D4; }
QPushButton#import_btn { background-color: #0078D4; color: white; border: none; }
QPushButton#export_btn { background-color: #28A745; color: white; border: none; }
QPushButton#cancel_btn { background-color: #C62828; color: white; border: none; }
QPushButton#cancel_btn:hover { background-color: #E53935; }
QPushButton:disabled { background-color: #1A1A1A; color: #555; border: 1px solid #222; }
QProgressBar {
    border: 1px solid #3D3D3D; border-radius: 8px;
    text-align: center; color: white; background-color: #1E1E1E;
}
QProgressBar::chunk { background-color: #0078D4; border-radius: 7px; }
"""

def apply_motion_blur(curr_frame, buffer, strength):
    if strength <= 0:
        return curr_frame
    buffer.append(curr_frame.astype(np.float32))
    max_frames = max(2, int(strength / 8)) 
    if len(buffer) > max_frames:
        buffer.pop(0)
    count = len(buffer)
    weights = np.linspace(0.1, 1.0, count)
    weights /= weights.sum()
    acc = np.zeros_like(buffer[0], dtype=np.float32)
    for frame, weight in zip(buffer, weights):
        acc += frame * weight
    return acc.astype(np.uint8)

class VideoThread(QThread):
    change_pixmap_signal = pyqtSignal(QImage)
    def __init__(self, path, blur_strength_provider):
        super().__init__()
        self.path = path
        self.running = True
        self.get_blur = blur_strength_provider
        self.buffer = []

    def run(self):
        cap = cv2.VideoCapture(self.path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        delay = int(1000 / fps)
        while self.running:
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self.buffer.clear()
                continue
            blended = apply_motion_blur(frame, self.buffer, self.get_blur())
            rgb = cv2.cvtColor(blended, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            img = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()
            self.change_pixmap_signal.emit(img.scaled(760, 420, Qt.AspectRatioMode.KeepAspectRatio))
            self.msleep(delay)
        cap.release()

    def stop(self):
        self.running = False
        self.wait()

class ExportThread(QThread):
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, input_file, output_file, fps, blur_strength):
        super().__init__()
        self.input_file = input_file
        self.output_file = output_file
        self.fps = int(fps)
        self.blur_strength = blur_strength
        self.process = None
        self.running = True

    def run(self):
        try:
            # PORTABLE FFMPEG LOGIC
            ffmpeg_exe = resource_path("ffmpeg.exe")
            if not os.path.exists(ffmpeg_exe):
                ffmpeg_exe = "ffmpeg" # Fallback to system path

            cap = cv2.VideoCapture(self.input_file)
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
            cap.release()

            blur_frames = max(1, int(self.blur_strength / 8))
            filter_str = f"fps={self.fps}"
            if blur_frames > 1:
                filter_str += f",tmix=frames={blur_frames}:weights='1 2 3 4 5 6 7 8 9 10'"

            cmd = [
                ffmpeg_exe, "-y", "-i", self.input_file,
                "-vf", filter_str,
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                "-pix_fmt", "yuv420p", self.output_file
            ]

            self.process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            for line in self.process.stdout:
                if not self.running: break
                match = re.search(r"frame=\s*(\d+)", line)
                if match:
                    self.progress_signal.emit(min(int((int(match.group(1)) / total) * 100), 99))

            self.process.wait()
            if self.running and self.process.returncode == 0:
                self.finished_signal.emit(self.output_file)
            elif not self.running:
                self.error_signal.emit("Render Cancelled")
        except Exception as e:
            self.error_signal.emit(str(e))

    def stop(self):
        self.running = False
        if self.process:
            self.process.terminate()
            self.process.kill()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FrameForge")
        self.setFixedSize(980, 650) 
        self.setStyleSheet(DARK_STYLE)
        
        # Apply Icon
        app_icon = load_icon()
        self.setWindowIcon(app_icon)

        self.video_path = None
        self.preview_thread = None
        self.export_thread = None
        self.init_ui()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.video_label = QLabel("Import video to see ultra smooth blur")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background:#000; border:2px dashed #3D3D3D; border-radius:12px;")
        self.video_label.setFixedSize(940, 420)
        layout.addWidget(self.video_label)

        controls = QFrame()
        h = QHBoxLayout(controls)

        self.import_btn = QPushButton("Import Video")
        self.import_btn.setObjectName("import_btn")
        self.import_btn.clicked.connect(self.import_video)

        self.fps_combo = QComboBox()
        self.fps_combo.addItems(["60", "90", "120", "240", "360"])

        self.blur_slider = QSlider(Qt.Orientation.Horizontal)
        self.blur_slider.setRange(0, 100)
        self.blur_slider.setValue(40)
        self.blur_label = QLabel("Motion Blur: 40")
        self.blur_slider.valueChanged.connect(lambda v: self.blur_label.setText(f"Motion Blur: {v}"))

        self.export_btn = QPushButton("Render")
        self.export_btn.setObjectName("export_btn")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.export_video)

        self.cancel_btn = QPushButton("Cancel Rendering")
        self.cancel_btn.setObjectName("cancel_btn")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_render)

        h.addWidget(self.import_btn); h.addWidget(QLabel("FPS:")); h.addWidget(self.fps_combo)
        h.addWidget(self.blur_label); h.addWidget(self.blur_slider); h.addWidget(self.export_btn); h.addWidget(self.cancel_btn)
        layout.addWidget(controls)

        self.progress = QProgressBar()
        layout.addWidget(self.progress)

    def import_video(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select Video", "", "Videos (*.mp4 *.mkv *.avi)")
        if file:
            self.video_path = file
            self.export_btn.setEnabled(True)
            if self.preview_thread: self.preview_thread.stop()
            self.preview_thread = VideoThread(file, lambda: self.blur_slider.value())
            self.preview_thread.change_pixmap_signal.connect(self.update_preview)
            self.preview_thread.start()

    def update_preview(self, img):
        self.video_label.setPixmap(QPixmap.fromImage(img))

    def export_video(self):
        save, _ = QFileDialog.getSaveFileName(self, "Save", "output.mp4", "MP4 (*.mp4)")
        if save:
            self.export_btn.setEnabled(False); self.cancel_btn.setEnabled(True); self.import_btn.setEnabled(False)
            self.export_thread = ExportThread(self.video_path, save, self.fps_combo.currentText(), self.blur_slider.value())
            self.export_thread.progress_signal.connect(self.progress.setValue)
            self.export_thread.finished_signal.connect(self.done)
            self.export_thread.error_signal.connect(self.on_error)
            self.export_thread.start()

    def cancel_render(self):
        if self.export_thread:
            self.export_thread.stop()
            self.cancel_btn.setEnabled(False)

    def on_error(self, msg):
        self.progress.setValue(0); self.export_btn.setEnabled(True); self.cancel_btn.setEnabled(False); self.import_btn.setEnabled(True)
        QMessageBox.warning(self, "Render Status", f"Error: {msg}")

    def done(self, path):
        self.progress.setValue(100); self.export_btn.setEnabled(True); self.cancel_btn.setEnabled(False); self.import_btn.setEnabled(True)
        QMessageBox.information(self, "Success", "Saved successfully!")

if __name__ == "__main__":
    # 1. Force Taskbar Icon identity
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Seyrix.FrameForge.Blur.1")
    except Exception:
        pass

    app = QApplication(sys.argv)
    
    # 2. Load and set Global App Icon
    icon = load_icon()
    app.setWindowIcon(icon)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())