"""The VPS guard for the rich engine: restarts rich-duval when the heartbeat is stale OR when the engine is alive but blind.

Blind means the heartbeat is fresh but no launch has been logged for BLIND_S seconds while the service has been up longer than
that. On 2026-10-28 the home engine ran 7 hours with a live heartbeat and a dead resolver and nobody restarted it; a heartbeat is
not a feed. Runs from rich-guard.timer every 5 minutes. Logs to monitor/guard.log.
"""
import json
import os
import subprocess
import time
from datetime import datetime, timezone

ROOT = "/srv/rich"
HB = os.path.join(ROOT, "monitor", "heartbeat.json")
LOG = os.path.join(ROOT, "monitor", "guard.log")
STALE_S = 120
BLIND_S = 600


def iso_age(s):
    if not s:
        return None
    t = datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
    return time.time() - t


def service_uptime():
    out = subprocess.run(["systemctl", "show", "rich-duval", "-p", "ActiveEnterTimestampMonotonic", "--value"], capture_output=True, text=True).stdout.strip()
    if not out or out == "0":
        return None
    return time.monotonic() - int(out) / 1e6


def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + " " + msg + "\n")


def main():
    active = subprocess.run(["systemctl", "is-active", "rich-duval"], capture_output=True, text=True).stdout.strip()
    if active != "active":
        subprocess.run(["systemctl", "restart", "rich-duval"])
        log(f"service was {active}: restarted")
        return
    up = service_uptime()
    try:
        with open(HB, encoding="utf-8") as f:
            raw = f.read()
        hb = json.loads(raw) if raw.strip("\x00 \r\n\t") else {}
    except Exception as e:
        hb = {}
        log(f"heartbeat unreadable ({str(e)[:80]})")
    hb_age = iso_age(hb.get("ts"))
    ll_age = iso_age(hb.get("last_launch"))
    if up is not None and up > STALE_S and (hb_age is None or hb_age > STALE_S):
        subprocess.run(["systemctl", "restart", "rich-duval"])
        log(f"heartbeat stale ({hb_age}); restarted")
        return
    if up is not None and up > BLIND_S and (ll_age is None or ll_age > BLIND_S):
        subprocess.run(["systemctl", "restart", "rich-duval"])
        log(f"engine blind: last launch {ll_age} s ago, up {int(up)} s; restarted")
        return


if __name__ == "__main__":
    main()
