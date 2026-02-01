import tkinter as tk
from tkinter import ttk
import cv2
from PIL import Image, ImageTk
import threading
import time

# =========================
# Parameters
# =========================

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720

GRID_ROWS = 2
GRID_COLS = 2

CAMERAS = [
    {
        "ip": "192.168.xxx.yyy",
        "user": "admin",
        "password": "xxxxx",
        "path": ""
    },
    {
                "ip": "192.168.xxx.zzz",
        "user": "admin",
        "password": "yyyyy",
        "path": "11"
    }
]

# =========================
# Camera class
# =========================

class RtspCamera:
    def __init__(self, rtsp_url, index):
        self.rtsp_url = rtsp_url
        self.index = index
        self.cap = None
        self.running = False
        self.frame = None
        self.lock = threading.Lock()

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.cap is not None:
            self.cap.release()

    def _capture_loop(self):
        # RTSP connect
        self.cap = cv2.VideoCapture(self.rtsp_url)
        if not self.cap.isOpened():
            print(f"[Camera {self.index}] Failed to open: {self.rtsp_url}")
            return

        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            # BGR -> RGB
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            with self.lock:
                self.frame = frame

        self.cap.release()

    def get_frame(self):
        with self.lock:
            return self.frame.copy() if self.frame is not None else None


# =========================
# Main
# =========================

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("IP Camera Viewer")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")

        self.cell_width = WINDOW_WIDTH // GRID_COLS
        self.cell_height = WINDOW_HEIGHT // GRID_ROWS

        # Camera initialize
        self.cameras = []
        self._init_cameras()

        # Tkinter Label
        self.labels = []
        self._create_grid_labels()

        # frame rate
        self.update_interval_ms = 30 
        self._update_frames()

        # finalize
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _init_cameras(self):
        for i, cam in enumerate(CAMERAS):
            rtsp_url = self._build_rtsp_url(cam)
            print(f"[Camera {i}] RTSP URL: {rtsp_url}")
            camera = RtspCamera(rtsp_url, i)
            camera.start()
            self.cameras.append(camera)

    def _build_rtsp_url(self, cam_info):
        user = cam_info["user"]
        password = cam_info["password"]
        ip = cam_info["ip"]
        path = cam_info["path"]
        return f"rtsp://{user}:{password}@{ip}:554/{path}"

    def _create_grid_labels(self):
        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                idx = r * GRID_COLS + c
                if idx >= len(self.cameras):

                    label = ttk.Label(self.root, text="No Camera", anchor="center")
                else:
                    label = ttk.Label(self.root)
                label.place(x=c * self.cell_width,
                            y=r * self.cell_height,
                            width=self.cell_width,
                            height=self.cell_height)
                self.labels.append(label)

        self.photo_images = [None] * len(self.labels)

    def _update_frames(self):
        for i, label in enumerate(self.labels):
            if i >= len(self.cameras):
                continue

            cam = self.cameras[i]
            frame = cam.get_frame()
            if frame is None:
                continue

            # resize
            resized = cv2.resize(frame, (self.cell_width, self.cell_height))

            # PIL Image
            img = Image.fromarray(resized)
            photo = ImageTk.PhotoImage(image=img)


            self.photo_images[i] = photo


            label.configure(image=photo)

        self.root.after(self.update_interval_ms, self._update_frames)

    def on_close(self):
        for cam in self.cameras:
            cam.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
