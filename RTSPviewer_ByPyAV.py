import tkinter as tk
from tkinter import ttk
import av
import threading
import time
from PIL import Image, ImageTk

# =========================
# Parameter
# =========================

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720

RTSP_REFRESH_INTERVAL = 30

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
# PyAV Camera Class
# =========================

class PyAvCamera:
    def __init__(self, rtsp_url, index, refresh_interval):
        self.rtsp_url = rtsp_url
        self.index = index
        self.refresh_interval = refresh_interval
        self.container = None
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
        if self.container:
            self.container.close()

    def _connect(self):
        if self.container:
            self.container.close()

        self.container = av.open(self.rtsp_url, timeout=3)
        self.stream = self.container.streams.video[0]
        self.stream.thread_type = "AUTO"

        self.last_connect_time = time.time()
        print(f"[Camera {self.index}] RTSP connected via PyAV.")

    def _capture_loop(self):
        self._connect()

        while self.running:
            # Refresh connection
            if time.time() - self.last_connect_time > self.refresh_interval:
                print(f"[Camera {self.index}] Refreshing RTSP connection...")
                self._connect()

            try:
                for packet in self.container.demux(self.stream):
                    for frame in packet.decode():
                        img = frame.to_ndarray(format="rgb24")

                        with self.lock:
                            self.frame = img

                        if not self.running:
                            break
            except Exception as e:
                print(f"[Camera {self.index}] Error: {e}")
                time.sleep(1)
                self._connect()

        if self.container:
            self.container.close()

    def get_frame(self):
        with self.lock:
            return self.frame.copy() if self.frame is not None else None

# =========================
# Main App
# =========================

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("PyAV RTSP Viewer")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")

        self.cameras = []
        self.photo_images = []

        self.fullscreen_index = None

        self._init_cameras()
        self._create_camera_frames()

        self.update_interval_ms = 30
        self._update_frames()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _init_cameras(self):
        for i, cam in enumerate(CAMERAS):
            rtsp_url = self._build_rtsp_url(cam)
            camera = PyAvCamera(rtsp_url, i, RTSP_REFRESH_INTERVAL)
            camera.start()
            self.cameras.append(camera)

    def _build_rtsp_url(self, cam):
        return f"rtsp://{cam['user']}:{cam['password']}@{cam['ip']}:554/{cam['path']}"

    # -------------------------
    # GUI
    # -------------------------

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

            # クリックでフルスクリーン
            label.bind("<Button-1>", lambda e, idx=i: self.toggle_fullscreen(idx))

            self.photo_images.append(None)

    # -------------------------
    # Fullscreen
    # -------------------------

    def toggle_fullscreen(self, index):
        if self.fullscreen_index is not None:
            self.restore_layout()
            self.fullscreen_index = None
            return

        self.root.update_idletasks()
        win_w = self.root.winfo_width()
        win_h = self.root.winfo_height()

        self.fullscreen_index = index

        for i, cam in enumerate(CAMERAS):
            frame = cam["frame"]
            if i == index:
                frame.place(x=0, y=0, width=win_w, height=win_h)
            else:
                frame.place_forget()

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

    # -------------------------
    # Frame Update
    # -------------------------

    def _update_frames(self):
        for i, cam in enumerate(CAMERAS):
            camera = self.cameras[i]
            frame = camera.get_frame()
            if frame is None:
                continue

            # フルスクリーン時は Window サイズでリサイズ
            if self.fullscreen_index == i:
                win_w = self.root.winfo_width()
                win_h = self.root.winfo_height()
                resized = Image.fromarray(frame).resize((win_w, win_h))
            else:
                resized = Image.fromarray(frame).resize((cam["width"], cam["height"]))

            photo = ImageTk.PhotoImage(image=resized)
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
