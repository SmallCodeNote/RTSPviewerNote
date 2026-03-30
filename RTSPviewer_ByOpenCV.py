import tkinter as tk
from tkinter import ttk
import cv2
from PIL import Image, ImageTk
import threading
import time

# =========================
# Parameter
# =========================

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720

# RTSP refresh interval in sec.
RTSP_REFRESH_INTERVAL = 30

# Cameras info and layout
CAMERAS = [
    {
        "ip": "192.168.xxx.yyy",
        "user": "admin",
        "password": "xxxxx",
        "path": "",
        "top": 0,
        "left": 0,
        "width": 640,
        "height": 360,
        "label": None
    },
    {
        "ip": "192.168.xxx.zzz",
        "user": "admin",
        "password": "yyyyy",
        "path": "11",
        "top": 0,
        "left": 640,
        "width": 640,
        "height": 360,
        "label": None
    }
]


# =========================
# Class
# =========================

class RtspCamera:
    def __init__(self, rtsp_url, index, refresh_interval):
        self.rtsp_url = rtsp_url
        self.index = index
        self.refresh_interval = refresh_interval
        self.cap = None
        self.running = False
        self.frame = None
        self.lock = threading.Lock()
        self.last_connect_time = 0

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.cap is not None:
            self.cap.release()

    def _connect(self):
        if self.cap is not None:
            self.cap.release()
        self.cap = cv2.VideoCapture(self.rtsp_url)
        self.last_connect_time = time.time()
        print(f"[Camera {self.index}] RTSP connected.")

    def _capture_loop(self):
        self._connect()

        while self.running:
            if time.time() - self.last_connect_time > self.refresh_interval:
                print(f"[Camera {self.index}] Refreshing RTSP connection...")
                self._connect()

            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            with self.lock:
                self.frame = frame

        if self.cap is not None:
            self.cap.release()

    def get_frame(self):
        with self.lock:
            return self.frame.copy() if self.frame is not None else None

# =========================
# Main App
# =========================

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("IP Camera Viewer")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")

        self.cameras = []
        self.photo_images = []

        self._init_cameras()
        self._create_camera_frames()

        self.update_interval_ms = 30
        self._update_frames()

        self.fullscreen_index = None
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _init_cameras(self):
        for i, cam in enumerate(CAMERAS):
            rtsp_url = self._build_rtsp_url(cam)
            camera = RtspCamera(rtsp_url, i, RTSP_REFRESH_INTERVAL)
            camera.start()
            self.cameras.append(camera)

    def _build_rtsp_url(self, cam):
        return f"rtsp://{cam['user']}:{cam['password']}@{cam['ip']}:554/{cam['path']}"
    
    def toggle_fullscreen(self, index):

        if self.fullscreen_index is not None:
            self.restore_layout()
            self.fullscreen_index = None
            return

        # Get Window Size
        self.root.update_idletasks()
        win_w = self.root.winfo_width()
        win_h = self.root.winfo_height()
        
        self.fullscreen_index = index

        for i, cam in enumerate(CAMERAS):
            frame = cam["frame"]

            if i == index:
                frame.place(
                    x=0,
                    y=0,
                    width=win_w,
                    height=win_h
                )
            else:
                frame.place_forget()

        # Esc Key Event
        self.root.bind("<Escape>", lambda e: self.toggle_fullscreen(index))

    def restore_layout(self):
        for cam in CAMERAS:
            frame = cam["frame"]
            frame.place(
                x=cam["left"],
                y=cam["top"],
                width=cam["width"],
                height=cam["height"]
            )

        self.root.unbind("<Escape>")

    def _create_camera_frames(self):
        for i, cam in enumerate(CAMERAS):
            frame = tk.Frame(self.root, bg="#222222")
            frame.place(
                x=cam["left"],
                y=cam["top"],
                width=cam["width"],
                height=cam["height"]
            )
            cam["frame"] = frame

            label = ttk.Label(frame, text="Connecting...", anchor="center")
            label.place(x=0, y=0, relwidth=1, relheight=1)
            cam["label"] = label

            label.bind("<Button-1>", lambda e, idx=i: self.toggle_fullscreen(idx))

            self.photo_images.append(None)


    def _update_frames(self):
        for i, cam in enumerate(CAMERAS):
            camera = self.cameras[i]
            frame = camera.get_frame()
            if frame is None:
                continue

            # On Full screen
            if self.fullscreen_index == i:
                win_w = self.root.winfo_width()
                win_h = self.root.winfo_height()
                resized = cv2.resize(frame, (win_w, win_h))
            else:
                resized = cv2.resize(frame, (cam["width"], cam["height"]))

            img = Image.fromarray(resized)
            photo = ImageTk.PhotoImage(image=img)

            self.photo_images[i] = photo
            cam["label"].configure(image=photo, text="")

        self.root.after(self.update_interval_ms, self._update_frames)


    def on_close(self):
        for cam in self.cameras:
            cam.stop()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
