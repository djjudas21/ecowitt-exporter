"""
Smoke test for WH46D support.

Starts `ecowitt_exporter.py` as a subprocess on a random free port, POSTs a
canned WH46D push body from `test_fixtures/wh46d_post.txt`, and scrapes
`/metrics` to verify that all four PM series are emitted (PM1, PM2.5, PM4,
PM10 — each in realtime and avg_24h series) alongside the existing WH45
CO2/temp/humidity metrics.

Run directly: `python3 test_wh46d.py`
"""

import os
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
FIXTURE = REPO_ROOT / "test_fixtures" / "wh46d_post.txt"


def _pick_port() -> int:
    """Bind to port 0, grab the kernel-assigned port, release it."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_listening(port: int, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"exporter did not start listening on {port} within {timeout}s")


def main() -> int:
    body = FIXTURE.read_text().strip()
    # Sanity check: the fixture must contain all four WH46D PM keys.
    for k in ("pm1_co2", "pm1_24h_co2", "pm4_co2", "pm4_24h_co2"):
        assert k in body, f"fixture missing {k}"

    port = _pick_port()
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"

    # The exporter hardcodes port 8088 in app.run(); run the script under a
    # shim that rewrites that literal on the fly so the test can run
    # alongside a real exporter on 8088 (and two tests don't collide).
    src = (REPO_ROOT / "ecowitt_exporter.py").read_text()
    patched = src.replace("port=8088", f"port={port}")
    patched = patched.replace('host="0.0.0.0"', 'host="127.0.0.1"')
    if f"port={port}" not in patched:
        raise RuntimeError("failed to patch app.run port; source layout changed")

    proc = subprocess.Popen(
        [sys.executable, "-c", patched],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        _wait_listening(port)

        # POST the fixture as application/x-www-form-urlencoded (what the
        # Ecowitt gateway actually sends).
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/report",
            data=body.encode("ascii"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            assert resp.status == 200, f"unexpected status {resp.status}"

        # Scrape /metrics and assert all the WH46D metrics appear.
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/metrics", timeout=3
        ) as resp:
            metrics_text = resp.read().decode("utf-8")

        expected = [
            # PM1.0 (WH46D only)
            'ecowitt_pm1{sensor="co2",series="realtime",unit="μgm3"} 6.1',
            'ecowitt_pm1{sensor="co2",series="avg_24h",unit="μgm3"} 5.8',
            # PM2.5 (WH45 + WH46D)
            'ecowitt_pm25{sensor="co2",series="realtime",unit="μgm3"} 9.8',
            'ecowitt_pm25{sensor="co2",series="avg_24h",unit="μgm3"} 8.4',
            # PM4.0 (WH46D only)
            'ecowitt_pm4{sensor="co2",series="realtime",unit="μgm3"} 11.2',
            'ecowitt_pm4{sensor="co2",series="avg_24h",unit="μgm3"} 10.5',
            # PM10 (WH45 + WH46D)
            'ecowitt_pm10{sensor="co2",series="realtime",unit="μgm3"} 13.0',
            'ecowitt_pm10{sensor="co2",series="avg_24h",unit="μgm3"} 12.1',
            # CO2 (WH45 + WH46D)
            'ecowitt_co2{series="realtime",unit="ppm"} 623.0',
            'ecowitt_co2{series="avg_24h",unit="ppm"} 580.0',
        ]
        missing = [m for m in expected if m not in metrics_text]
        if missing:
            print("MISSING METRICS:")
            for m in missing:
                print(f"  {m}")
            print("\n--- /metrics (relevant lines) ---")
            for line in metrics_text.splitlines():
                if any(x in line for x in ("ecowitt_pm", "ecowitt_co2", "ecowitt_aqi")):
                    print(line)
            return 1

        print(f"OK — all {len(expected)} WH46D/WH45 metrics present")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
