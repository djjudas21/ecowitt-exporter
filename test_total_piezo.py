"""
Regression test for the WS90 `total_piezo` field.

GW2000A firmware V3.3.3 added a `total_piezo` field to the push body. The
exporter used to look up every *_piezo key in a `rainmaps` dict, so this
unknown key raised a KeyError and every POST /report returned 500.

Starts `ecowitt_exporter.py` as a subprocess on a random free port, POSTs a
V3.3.3 push body with the WS90 and WH52 fields plus `total_piezo`
(`test_fixtures/total_piezo_post.txt`), and scrapes `/metrics` to verify that
the POST returns 200 and that the rain and WH52 metrics are exported.

The exporter runs with the same interpreter as the test, so run it with one
that has `requirements.txt` installed, e.g.
`.venv/bin/python test_total_piezo.py`.
"""

import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from test_wh52 import _pick_port, _stderr_text, _wait_listening


REPO_ROOT = Path(__file__).resolve().parent
FIXTURE = REPO_ROOT / "test_fixtures" / "total_piezo_post.txt"

EXPECTED = [
    # total_piezo=31.453 (inches) converted to mm, labelled like the other
    # piezo keys
    'ecowitt_rain{sensor="total_piezo",unit="mm"} 798.9',
    'ecowitt_rain{sensor="yrain_piezo",unit="mm"} 639.3',
    'ecowitt_rain{sensor="mrain_piezo",unit="mm"} 17.9',
    'ecowitt_rain{sensor="last24hrain_piezo",unit="mm"} 1.0',
    'ecowitt_rain_state{sensor="srain_piezo"} 0.0',
    'ecowitt_wh90{sensor="ws90cap_volt",unit="volt"} 4.6',
    'ecowitt_soilmoisture{sensor="soil_ec_hum1",unit="percent"} 50.0',
    # soil_ec_temp1=62.78 (Fahrenheit) converted to Celsius
    'ecowitt_soiltemp{sensor="soil_ec_temp1",unit="c"} 17.1',
    'ecowitt_soilec{sensor="soil_ec1",unit="uscm"} 410.0',
    'ecowitt_batteryvoltage{sensor="soil_ec_batt1",unit="volt"} 1.6',
    'ecowitt_sensor_last_report_timestamp_seconds{sensor="soil_ec_hum1"}',
]


def main() -> int:
    """Run the exporter, POST the fixture and check /metrics."""
    body = FIXTURE.read_text(encoding="ascii").strip()

    port = _pick_port()
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    env["TEMPERATURE_UNIT"] = "c"
    env["RAIN_UNIT"] = "mm"

    # The exporter hardcodes port 8088 in app.run(), so run a copy of the
    # source with that literal rewritten (see test_wh52.py).
    src = (REPO_ROOT / "ecowitt_exporter.py").read_text(encoding="utf-8")
    patched = src.replace("port=8088", f"port={port}")
    patched = patched.replace('host="0.0.0.0"', 'host="127.0.0.1"')
    if f"port={port}" not in patched:
        raise RuntimeError("failed to patch app.run port; source layout changed")

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
            try:
                with urllib.request.urlopen(req, timeout=3) as resp:
                    status = resp.status
            except urllib.error.HTTPError as exc:
                status = exc.code

            with urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics", timeout=3) as resp:
                metrics_text = resp.read().decode("utf-8")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
        stderr_text = _stderr_text(stderr_file)

    errors = [] if status == 200 else [f"POST of {FIXTURE.name} returned {status}"]
    errors += [f"MISSING: {m}" for m in EXPECTED if m not in metrics_text]
    if errors:
        for e in errors:
            print(e)
        print("\n--- /metrics (rain and soil lines) ---")
        for line in metrics_text.splitlines():
            if not line.startswith("#") and ("rain" in line or "soil" in line):
                print(line)
        print(f"\n--- exporter stderr ---\n{stderr_text}")
        return 1

    print(f"OK - POST returned 200, all {len(EXPECTED)} metrics present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
