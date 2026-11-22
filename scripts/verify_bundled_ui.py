"""Prove the packaged app serves the built frontend and keeps the API intact.

Run after `npm run build` and copying `frontend/dist/*` into `unimonitor/static/`
(the Docker image and Windows installer do exactly that). Starts the real
uvicorn server so path resolution and content types are exercised, not mocked.

    python scripts/verify_bundled_ui.py
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "unimonitor" / "static"
ROOT_ELEMENT = '<div id="root">'
STARTUP_TIMEOUT = 45
failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "ok  " if condition else "FAIL"
    print(f"[{status}] {name}{f' — {detail}' if detail else ''}")
    if not condition:
        failures.append(name)


def fetch(url: str) -> tuple[int, str, bytes]:
    try:
        # Localhost only.
        with urllib.request.urlopen(url, timeout=10) as response:  # noqa: S310
            return response.status, response.headers.get("content-type", ""), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers.get("content-type", ""), exc.read()


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> int:
    index = STATIC / "index.html"
    check("frontend build is staged at unimonitor/static/index.html", index.is_file(), str(STATIC))
    if not index.is_file():
        print("\nRun `npm run build` and copy frontend/dist/* into unimonitor/static/ first.")
        return 1

    html = index.read_text()
    check("index.html ships the React root", ROOT_ELEMENT in html)

    port = free_port()
    env = {**os.environ, "UNIMONITOR_ENV": "test"}
    # Fixed argv, no shell, local-only server.
    server = subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "uvicorn", "unimonitor.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    base = f"http://127.0.0.1:{port}"
    try:
        ready, detail = _wait_until_ready(server, base)
        if not ready:
            print(f"server did not start\n{detail}")
            return 1
        _check_routes(base, html)
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()

    if failures:
        print(f"\n{len(failures)} check(s) failed: {', '.join(failures)}")
        return 1
    print("\nBundled UI and API both respond.")
    return 0


def _wait_until_ready(server: subprocess.Popen, base: str) -> tuple[bool, str]:
    """Poll the health route until it answers, the process dies, or time runs out."""
    deadline = time.time() + STARTUP_TIMEOUT
    while time.time() < deadline:
        if server.poll() is not None:
            break
        try:
            if fetch(f"{base}/api/v1/health")[0] == 200:
                return True, ""
        except OSError:
            pass
        time.sleep(0.5)
    stderr = (server.stderr.read() if server.stderr else b"").decode(errors="replace")[-2000:]
    return False, stderr


def _check_routes(base: str, html: str) -> None:
    """Every assertion this script makes against the running app."""
    status, ctype, body = fetch(f"{base}/")
    check("GET / returns the app shell", status == 200 and "text/html" in ctype, f"{status} {ctype}")
    check("GET / renders index.html", ROOT_ELEMENT in body.decode(errors="replace"))

    asset = re.search(r"/assets/[\w.\-]+\.js", html)
    check("index.html references a hashed asset", asset is not None)
    if asset:
        status, ctype, _ = fetch(base + asset.group(0))
        check("hashed JS asset is served", status == 200 and "javascript" in ctype, f"{status} {ctype}")

    status, ctype, body = fetch(f"{base}/clouds")
    check(
        "deep link /clouds falls back to the SPA",
        status == 200 and ROOT_ELEMENT in body.decode(errors="replace"),
        f"{status} {ctype}",
    )

    status, ctype, body = fetch(f"{base}/api/v1/health")
    check(
        "API health still returns JSON",
        status == 200 and "application/json" in ctype and json.loads(body)["status"] == "ok",
        f"{status} {ctype}",
    )

    status, ctype, _ = fetch(f"{base}/api/v1/dashboard/clouds")
    check("authenticated API route is not shadowed by the SPA", status == 401, f"{status} {ctype}")

    # routes declared with an empty path ("/api/v1/tenants") were the ones a
    # catch-all SPA route used to hide
    status, ctype, _ = fetch(f"{base}/api/v1/tenants")
    check("collection route /api/v1/tenants still answers (401, not SPA 404)", status == 401, f"{status} {ctype}")

    status, ctype, _ = fetch(f"{base}/api/v1/does-not-exist")
    check("unknown API path stays a 404 JSON error", status == 404, f"{status} {ctype}")


if __name__ == "__main__":
    raise SystemExit(main())
