"""
start.py: start the whole CodeREAD system with one command.

    python start.py            (from the repo root; Windows: double-click start.bat)

What it does, in order:
  1. Builds the dashboard (npm install the first time, then npm run build) in
     live-data mode, so the page talks to the real API.
  2. Starts the monitor:        python src/ReadFlare/main.py
  3. Starts the API + website:  python dashboard/server/api.py  ->  http://localhost:5000
  4. Opens http://localhost:5000 in your browser.
Press Ctrl+C once to stop everything.

Flags:
  --no-monitor   start only the API and the dashboard (no USITC polling)
  --no-build     reuse the existing dashboard/dist build (faster restarts)
  --no-browser   don't open a browser tab

Needs Python 3.11+ (diff.py uses StrEnum), Node 18+, and the packages in
requirements.txt (installed automatically if missing).
"""

import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DASHBOARD = ROOT / "dashboard"
URL = "http://localhost:5000"


def say(msg):
    print(f"[start] {msg}", flush=True)


REQUIREMENTS = ROOT / "requirements.txt"
# import name for each package in requirements.txt (they can differ from the pip name)
REQUIRED_IMPORTS = ["flask", "requests"]


def check_python():
    if sys.version_info < (3, 11):
        sys.exit(f"Python 3.11 or newer is needed (you have {sys.version.split()[0]}). "
                 "On Windows try: py -3.12 start.py")

    missing = []
    for name in REQUIRED_IMPORTS:
        try:
            __import__(name)
        except ImportError:
            missing.append(name)
    if not missing:
        return

    say(f"Installing Python packages from requirements.txt (missing: {', '.join(missing)})...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)])
    except subprocess.CalledProcessError:
        # Common on Linux: the system Python refuses pip installs ("externally managed").
        sys.exit("Could not install the Python packages. Create a virtual environment and try again:\n"
                 "  python -m venv venv\n"
                 "  source venv/bin/activate        (Windows: venv\\Scripts\\activate)\n"
                 "  pip install -r requirements.txt\n"
                 "  python start.py")


def check_pdftotext():
    # changerecord.py reads Change Record PDFs with pdftotext (from Poppler).
    # Without it the monitor still runs, but every change is "not listed in
    # change record", with no effective date or legal source.
    if shutil.which("pdftotext") is None:
        say("WARNING: pdftotext was not found, so Change Record dates and sources will be missing.")
        say("  Windows: install Poppler and add its bin folder to PATH")
        say("  Fedora:  sudo dnf install poppler-utils")
        say("  Ubuntu:  sudo apt install poppler-utils")
        say("  macOS:   brew install poppler")


def build_dashboard():
    # On Windows npm is npm.cmd; shutil.which finds the right one.
    npm = shutil.which("npm")
    if npm is None:
        sys.exit("npm was not found. Install Node.js 18+ from https://nodejs.org and try again.")
    if not (DASHBOARD / "node_modules" / "react").exists():
        say("Installing dashboard packages (first run only)...")
        subprocess.check_call([npm, "install"], cwd=DASHBOARD)
    say("Building the dashboard...")
    # VITE_USE_MOCK=false: the built page calls the live API instead of the snapshot.
    env = {**os.environ, "VITE_USE_MOCK": "false"}
    subprocess.check_call([npm, "run", "build"], cwd=DASHBOARD, env=env)


def wait_for(url, seconds=30):
    """Poll until the API answers, so the browser doesn't open on an error page."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def _stop(_signum, _frame):
    # Closing the window or `kill` sends SIGTERM; treat it like Ctrl+C.
    raise KeyboardInterrupt


def main():
    signal.signal(signal.SIGTERM, _stop)
    args = set(sys.argv[1:])
    check_python()
    check_pdftotext()
    if "--no-build" not in args or not (DASHBOARD / "dist" / "index.html").exists():
        build_dashboard()

    # -u: unbuffered, so both programs' output shows up right away in this window.
    procs = []
    if "--no-monitor" not in args:
        say("Starting the monitor (src/ReadFlare/main.py)...")
        procs.append(("monitor", subprocess.Popen(
            [sys.executable, "-u", str(ROOT / "src" / "ReadFlare" / "main.py")], cwd=ROOT)))
        # No need to wait for the monitor: api.py runs database.init_db() itself.

    say("Starting the API and dashboard (dashboard/server/api.py)...")
    procs.append(("api", subprocess.Popen(
        [sys.executable, "-u", str(DASHBOARD / "server" / "api.py"), "--no-debug"], cwd=ROOT)))

    if wait_for(f"{URL}/api/status"):
        say(f"Dashboard ready at {URL}  (Ctrl+C to stop)")
        if "--no-browser" not in args:
            webbrowser.open(URL)
    else:
        say("The API did not answer within 30 seconds; check the messages above.")

    try:
        # Stay alive while both run; if one exits, say so and stop the rest.
        while True:
            for name, p in procs:
                if p.poll() is not None:
                    say(f"The {name} stopped (exit code {p.returncode}). Stopping everything.")
                    raise KeyboardInterrupt
            time.sleep(1)
    except KeyboardInterrupt:
        say("Shutting down...")
        for _name, p in procs:
            if p.poll() is None:
                p.terminate()
        for _name, p in procs:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    main()