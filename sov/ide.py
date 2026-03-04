#!/usr/bin/env python3
"""
sov-ide  →  Sovereign Browser IDE
AMALLO agent + RealSense vision in chat + auto-start UI preview window.

  sov --ide
  sov-ide

Launches:
  - sov --ui preview window on port 7071 (auto)
  - RealSense vision capture thread (if camera available)
  - sovereign-control.html IDE on port 7070
"""
import sys, os, http.server, threading, webbrowser, socketserver, time

PINK = "\033[38;2;255;105;180m"
CYAN = "\033[38;2;0;220;255m"
LIME = "\033[38;2;57;255;100m"
GOLD = "\033[38;2;255;200;50m"
GRAY = "\033[38;2;85;85;105m"
RST  = "\033[0m"
BOLD = "\033[1m"

BANNER = f"""
{PINK}{BOLD}  ╔══════════════════════════════════════════════╗
  ║  SOV-IDE  ·  SOVEREIGN IDE                  ║
  ╚══════════════════════════════════════════════╝{RST}
"""

IDE_PORT     = 7070
SERVE_FILE   = "sovereign-control.html"


# ── RealSense Vision Thread ────────────────────────────────────────────────────
def _start_realsense():
    """
    Tries to start Intel RealSense depth + RGB capture.
    Streams frames to the agent context via sov --ui push endpoint.
    Silently skips if pyrealsense2 not installed or camera not connected.
    """
    try:
        import pyrealsense2 as rs
        import numpy as np
        from sov.ui import push as ui_push
        import base64, io

        pipeline = rs.pipeline()
        config = rs.config()
        config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
        config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
        pipeline.start(config)

        print(f"  {LIME}✓{RST}  RealSense : camera online (640×480 @ 30fps)")

        frame_interval = 1.0  # push a vision frame every 1s to agent context
        last_push = 0.0

        while True:
            frames = pipeline.wait_for_frames()
            now = time.time()
            if now - last_push < frame_interval:
                continue
            last_push = now

            color_frame = frames.get_color_frame()
            if not color_frame:
                continue

            # Encode frame as base64 JPEG for the preview window
            import cv2
            img = np.asanyarray(color_frame.get_data())
            _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 60])
            b64 = base64.b64encode(buf).decode()
            html = f'<img src="data:image/jpeg;base64,{b64}" style="width:100%;height:auto;display:block">'
            ui_push(html=html, label="realsense vision frame")

    except ImportError:
        print(f"  {GRAY}○  RealSense: pyrealsense2 not installed — vision disabled{RST}")
    except Exception as e:
        print(f"  {GRAY}○  RealSense: {e} — vision disabled{RST}")


# ── IDE HTTP Server ────────────────────────────────────────────────────────────
def main():
    print(BANNER)

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    html_path = os.path.join(here, SERVE_FILE)

    if not os.path.exists(html_path):
        print(f"  [sov-ide] {SERVE_FILE} not found at {here}")
        sys.exit(1)

    # 1. Auto-start preview window (sov --ui) on port 7071
    from sov.ui import main as ui_main
    ui_thread = threading.Thread(
        target=ui_main, kwargs={"open_browser": False}, daemon=True
    )
    ui_thread.start()
    print(f"  {LIME}✓{RST}  Preview  : http://localhost:7071  (auto-started)")

    # 2. Start RealSense vision thread
    rs_thread = threading.Thread(target=_start_realsense, daemon=True)
    rs_thread.start()

    # 3. Serve IDE
    class IDEHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=here, **kwargs)
        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self.path = f"/{SERVE_FILE}"
            super().do_GET()
        def log_message(self, *_): pass

    url = f"http://localhost:{IDE_PORT}"
    print(f"  {LIME}✓{RST}  IDE      : {url}")
    print(f"  {LIME}✓{RST}  Agent    : AMALLO via axismundi.fun")
    print(f"  {GRAY}    Ctrl+C to stop all{RST}\n")

    def _open():
        time.sleep(0.7)
        webbrowser.open(url)
        time.sleep(0.3)
        webbrowser.open("http://localhost:7071")
    threading.Thread(target=_open, daemon=True).start()

    class ReuseTCP(socketserver.TCPServer):
        allow_reuse_address = True

    with ReuseTCP(("", IDE_PORT), IDEHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print(f"\n  {GRAY}[sov-ide] stopped.{RST}")


if __name__ == "__main__":
    main()

