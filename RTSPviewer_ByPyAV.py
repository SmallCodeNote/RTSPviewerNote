import tkinter as tk
from tkinter import ttk
import av
import threading
import time
from PIL import Image, ImageTk, ImageDraw, ImageFont

# =========================
# Parameter
# =========================

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720

RTSP_REFRESH_INTERVAL = 30
RECONNECT_INTERVAL = 10 

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
        self.connected = False

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.container:
            self.container.close()

    def _connect(self):
        """RTSP connect"""
        if self.container:
            self.container.close()

        print(f"[Camera {self.index}] Connecting RTSP...")

        try:
            self.container = av.open(self.rtsp_url, timeout=3)
            self.stream = self.container.streams.video[0]
            self.stream.thread_type = "AUTO"
            self.last_connect_time = time.time()
            self.connected = True
            print(f"[Camera {self.index}] RTSP connected.")
        except Exception as e:
            self.connected = False
            print(f"[Camera {self.index}] Connection failed: {e}")
            raise

    def _capture_loop(self):
        while self.running:
            if not self.connected:
                try:
                    self._connect()
                except:
                    time.sleep(RECONNECT_INTERVAL)
                    continue

            try:
                for packet in self.container.demux(self.stream):
                    for frame in packet.decode():
                        img = frame.to_ndarray(format="rgb24")
                        with self.lock:
                            self.frame = img

                        if not self.running:
                            break

                print(f"[Camera {self.index}] Stream ended.")
                self.connected = False

            except Exception as e:
                print(f"[Camera {self.index}] Error: {e}")
                self.connected = False
                time.sleep(RECONNECT_INTERVAL)

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

        self.overlay_font = ImageFont.load_default()

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
            frame.place(x=cam["left"], y=cam["top"], width=cam["width"], height=cam["height"])
            cam["frame"] = frame

            video_label = tk.Label(frame, bg="black")
            video_label.place(x=0, y=0, relwidth=1, relheight=1)
            cam["video_label"] = video_label

            video_label.bind("<Button-1>", lambda e, idx=i: self.toggle_fullscreen(idx))

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
            frame.place(x=cam["left"], y=cam["top"], width=cam["width"], height=cam["height"])
        self.root.unbind("<Escape>")

    # -------------------------
    # Frame Update
    # -------------------------
    def _update_frames(self):
        for i, cam in enumerate(CAMERAS):
            camera = self.cameras[i]

            # ======== Status Text ========
            if not camera.connected:
                center_text = "Camera Not Found"
            else:
                frame = camera.get_frame()
                center_text = "Connecting..." if frame is None else ""

            # ======== Create frame ========
            if camera.connected and frame is not None:
                img = Image.fromarray(frame)
            else:
                # Background
                if self.fullscreen_index == i:
                    w = self.root.winfo_width()
                    h = self.root.winfo_height()
                else:
                    w = cam["width"]
                    h = cam["height"]
                img = Image.new("RGB", (max(w, 1), max(h, 1)), "black")

            # ======== resize ========
            if self.fullscreen_index == i:
                win_w = self.root.winfo_width()
                win_h = self.root.winfo_height()
                resized = img.resize((max(win_w, 1), max(win_h, 1)))
            else:
                resized = img.resize((cam["width"], cam["height"]))

            draw = ImageDraw.Draw(resized, "RGBA")

            # ============================================================
            # Cameras Label View
            # ============================================================
            right_label = cam.get("label", "")
            if right_label:
                margin = 8

                # Get TextBox Size
                bbox = draw.textbbox((0, 0), right_label, font=self.overlay_font)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]

                x2 = resized.width - margin
                x1 = x2 - tw - margin * 2
                y1 = margin
                y2 = y1 + th + margin * 2

                draw.rectangle([(x1, y1), (x2, y2)], fill=(0, 0, 0, 160))

                draw.text(
                    (x2 - margin, y1 + margin),
                    right_label,
                    font=self.overlay_font,
                    fill=(255, 255, 255, 255),
                    anchor="ra"
                )

            # ============================================================
            # Status Text（Camera Not Found / Connecting...）
            # ============================================================
            if center_text:
                max_width = resized.width * 0.9  # 画面の 90% 以内に収める
                font_size = 10
                font = ImageFont.load_default()

                try:
                    while True:
                        test_font = ImageFont.truetype("arial.ttf", font_size)
                        bbox = draw.textbbox((0, 0), center_text, font=test_font)
                        tw = bbox[2] - bbox[0]
                        if tw > max_width:
                            break
                        font = test_font
                        font_size += 2
                except:
                    font = self.overlay_font

                bbox = draw.textbbox((0, 0), center_text, font=font)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]

                cx = resized.width // 2
                cy = resized.height // 2

                # BackGround
                draw.rectangle(
                    [(cx - tw//2 - 20, cy - th//2 - 20),
                    (cx + tw//2 + 20, cy + th//2 + 20)],
                    fill=(0, 0, 0, 160)
                )

                draw.text(
                    (cx, cy),
                    center_text,
                    font=font,
                    fill=(255, 255, 255, 255),
                    anchor="mm"
                )

            # ============================================================

            photo = ImageTk.PhotoImage(image=resized)
            self.photo_images[i] = photo
            cam["video_label"].configure(image=photo)

        self.root.after(self.update_interval_ms, self._update_frames)


    def on_close(self):
        for cam in self.cameras:
            cam.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
