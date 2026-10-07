"""Start Sentinel Street and open the dashboard.

    python run.py                 # http://127.0.0.1:8000, opens a browser window
    python run.py --no-browser    # server only
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser

import uvicorn

CHROME_APP = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def open_dashboard(url: str) -> None:
    """Prefer a chromeless Chrome 'app' window; fall back to the default browser."""
    time.sleep(1.5)
    chrome = CHROME_APP if sys.platform == "darwin" else shutil.which("google-chrome") or shutil.which("chrome")
    if chrome and os.path.exists(chrome):
        try:
            subprocess.Popen([chrome, f"--app={url}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except OSError:
            pass
    webbrowser.open(url)


def ensure_camera_permission() -> None:
    """macOS shows the camera permission prompt only from the main thread, but the server opens the
    camera from a worker thread. Ask here on every start, before the server starts, so the prompt can
    appear: permission belongs to the terminal app that runs this, not to the project, so a remembered
    "granted" would be wrong as soon as it is started from a different terminal."""
    if sys.platform != "darwin" or os.environ.get("SENTINEL_VIDEO"):
        return
    import cv2

    print("Checking camera access (macOS may ask you to allow it)…")
    # The first try only *sends* the request; macOS shows its prompt while we keep trying, so give the
    # person time to click Allow before the server starts.
    deadline = time.monotonic() + 30
    while True:
        capture = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)
        granted = capture.isOpened() and capture.read()[0]
        capture.release()
        if granted or time.monotonic() > deadline:
            break
        print("Waiting for camera access: click Allow if macOS asks (up to 30 s)…", flush=True)
        time.sleep(2)
    if granted:
        print("Camera access OK")
    else:
        print("Camera not available yet. If you denied access, allow it in System Settings > "
              "Privacy & Security > Camera for the app running this terminal, then restart.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sentinel Street dashboard")
    # Bound to localhost by default: the camera feed should not be reachable from the network.
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--video", help="play this video/image file instead of the webcam (demo mode)")
    args = parser.parse_args()
    if args.video:
        os.environ["SENTINEL_VIDEO"] = os.path.abspath(args.video)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    ensure_camera_permission()
    if not args.no_browser:
        threading.Thread(target=open_dashboard, args=(f"http://127.0.0.1:{args.port}",), daemon=True).start()
    uvicorn.run("sentinel.server:app", host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
