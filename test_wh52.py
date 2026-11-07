"""
Smoke test for WH52 support.

Starts `ecowitt_exporter.py` as a subprocess on a random free port, POSTs a
WH52 push body captured from a GW2000A gateway (`test_fixtures/wh52_post.txt`),
and scrapes `/metrics` to verify that the WH52 moisture, temperature, EC and
battery metrics are exported, and that its raw AD readings are not.

The exporter runs with the same interpreter as the test, so run it with one
that has `requirements.txt` installed, e.g. `.venv/bin/python test_wh52.py`.
"""

import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
FIXTURE = REPO_ROOT / "test_fixtures" / "wh52_post.txt"

EXPECTED = [
    'ecowitt_soilmoisture{sensor="soil_ec_hum1",unit="percent"} 32.0',
    # soil_ec_temp1=60.26 (Fahrenheit) converted to Celsius
    'ecowitt_soiltemp{sensor="soil_ec_temp1",unit="c"} 15.7',
    'ecowitt_soilec{sensor="soil_ec1",unit="uscm"} 320.0',
    'ecowitt_batteryvoltage{sensor="soil_ec_batt1",unit="volt"} 1.6',
    'ecowitt_sensor_last_report_timestamp_seconds{sensor="soil_ec_hum1"}',
    'ecowitt_sensor_last_report_timestamp_seconds{sensor="soil_ec_batt1"}',
]

# The raw AD readings must not be exported
UNEXPECTED = ['soil_ec_hum_ad1', 'soil_ec_ad1']


def _pick_port() -> int:
    """Bind to port 0, grab the kernel-assigned port, release it."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _stderr_text(stderr_file) -> str:
    stderr_file.seek(0)
    return stderr_file.read().decode("utf-8", errors="replace").strip()


def _wait_listening(port: int, proc: subprocess.Popen, stderr_file,
                    timeout: float = 5.0) -> None:
    """Wait for the exporter to accept connections, or fail with its stderr."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(
                f"exporter exited with code {proc.returncode} before listening "
                f"on {port}:\n{_stderr_text(stderr_file)}"
            )
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(
        f"exporter did not start listening on {port} within {timeout}s:\n"
        f"{_stderr_text(stderr_file)}"
    )


def main() -> int:
    """Run the exporter, POST the fixture and check /metrics."""
    body = FIXTURE.read_text(encoding="ascii").strip()

    port = _pick_port()
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    env["TEMPERATURE_UNIT"] = "c"

    # The exporter hardcodes port 8088 in app.run(), so run a copy of the
    # source with that literal rewritten. This lets the test run alongside a
    # real exporter on 8088.
    src = (REPO_ROOT / "ecowitt_exporter.py").read_text(encoding="utf-8")
    patched = src.replace("port=8088", f"port={port}")
    patched = patched.replace('host="0.0.0.0"', 'host="127.0.0.1"')
    if f"port={port}" not in patched:
        raise RuntimeError("failed to patch app.run port; source layout changed")

    # Keep the exporter's stderr in a temporary file, so a crash on startup
    # (e.g. a missing dependency) is reported instead of a bare timeout.
    with tempfile.TemporaryFile() as stderr_file, subprocess.Popen(
        [sys.executable, "-c", patched],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=stderr_file,
    ) as proc:
        try:
            _wait_listening(port, proc, stderr_file)

            # POST the fixture as application/x-www-form-urlencoded, as the
            # gateway does.
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/report",
                data=body.encode("ascii"),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                assert resp.status == 200, f"unexpected status {resp.status}"

            with urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics", timeout=3) as resp:
                metrics_text = resp.read().decode("utf-8")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()

    missing = [m for m in EXPECTED if m not in metrics_text]
    present = [k for k in UNEXPECTED if f'"{k}"' in metrics_text]
    if missing or present:
        for m in missing:
            print(f"MISSING: {m}")
        for k in present:
            print(f"UNEXPECTED: {k}")
        print("\n--- /metrics (soil lines) ---")
        for line in metrics_text.splitlines():
            if "soil" in line:
                print(line)
        return 1

    print(f"OK - all {len(EXPECTED)} WH52 metrics present, raw AD readings ignored")
    return 0


if __name__ == "__main__":
    sys.exit(main())
