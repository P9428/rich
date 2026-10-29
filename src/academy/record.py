"""The pinned record: the engine's path tape (journal/paths/<day>.jsonl) frozen into arrays, one file a day, each with the sha256 of
the bytes it was built from. A grown tape is a new record, never an edit: today's file is rebuilt when its bytes change, a finished
day is built once. The arrays are what the arena vectorises over; the per-launch columns are the only keys a cell may use, and every
one of them is known at the launch's create or at the entry mark (the look-ahead rule).

Columns (per launch)             Arrays (N x M marks, NaN past the path's end)
  ts        epoch seconds          T   seconds after create
  mint      str                    VS  virtual SOL on the curve
  match     matched terms (int)    VT  virtual tokens
  pump      mint ends in 'pump'    RS  real SOL on the curve (outside buyers' SOL)
  plain     pool pump, no mayhem
  mcap0     USD at create
  init      creator's buy at create (SOL)
  v0s, v0t  the create message's reserves
  cls       0 none · 1 narrative · 2 dev · 3 tech · 4 celebrity   (five.classify)
  gate      0 unknown · 1 dead · 2 live · 3 resist                 (five.Meta at the create)
  fam       0 empty · 1 sniped · 2 seeded · 3 bundled              (the launcher's family, see FAMILIES)
  hour      UTC hour at create
"""
import calendar
import glob
import hashlib
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))
import common as C   # noqa: E402
import five as F     # noqa: E402

RDIR = C.path("state", "academy", "record")
M = 95                  # marks kept per path (180 s at 2 s is 90 or 91)
CLS = {"none": 0, "narrative": 1, "dev": 2, "tech": 3, "celebrity": 4}
GATE = {"unknown": 0, "dead": 1, "live": 2, "resist": 3}
# the family is the launcher's own script as the tape shows it at the first mark: did the creator buy at create, and had anyone
# bought by the first mark (a buy inside the create's own second is a bundle or a sniper, not a stranger reading the news)
FAMILIES = ["empty", "sniped", "seeded", "bundled"]
COLS = ("ts", "match", "pump", "plain", "mcap0", "init", "v0s", "v0t", "cls", "gate", "fam", "hour")


def sha(file):
    h = hashlib.sha256()
    with open(file, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _epoch(ts):
    return float(calendar.timegm(time.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S")))


def family(init_sol, r0):
    if (init_sol or 0) >= F.DEV_SOL:
        return 3
    if (init_sol or 0) > 0:
        return 2
    return 1 if (r0 or 0) > 0 else 0


def build(file):
    """One day's path file into arrays. Torn or interleaved lines are skipped (the engine appends while this runs)."""
    rows = []
    with open(file, "rb") as fh:
        for raw in fh.read().splitlines():
            if not raw.strip():
                continue
            try:
                p = json.loads(raw.decode("utf-8", "ignore"))
            except Exception:
                continue
            if p.get("marks") and p.get("v0"):
                rows.append(p)
    rows.sort(key=lambda p: p["ts"])
    n = len(rows)
    col = {k: np.zeros(n) for k in COLS}
    mint = np.empty(n, dtype=object)
    T, VS, VT, RS = (np.full((n, M), np.nan) for _ in range(4))
    meta = F.Meta()
    for i, p in enumerate(rows):
        t0 = _epoch(p["ts"])
        marks = p["marks"][:M]
        a = np.asarray(marks, dtype=float)
        T[i, :len(a)], VS[i, :len(a)], VT[i, :len(a)], RS[i, :len(a)] = a[:, 0], a[:, 1], a[:, 2], a[:, 3]
        mint[i] = p["mint"]
        col["ts"][i] = t0
        col["match"][i] = len(p.get("match") or [])
        col["pump"][i] = p["mint"].endswith("pump")
        col["plain"][i] = p.get("pool") in (None, "pump") and not p.get("mayhem")
        col["mcap0"][i] = p.get("mcap0_usd") if p.get("mcap0_usd") is not None else np.nan
        col["init"][i] = p.get("init_sol") or 0
        col["v0s"][i], col["v0t"][i] = p["v0"]
        col["cls"][i] = CLS[F.classify(p.get("name"), p.get("sym") or p.get("symbol"), p.get("init_sol"), p.get("match") or [])]
        col["gate"][i] = GATE[meta.state(t0)[0]]
        col["fam"][i] = family(p.get("init_sol"), marks[0][3])
        col["hour"][i] = int(time.gmtime(t0).tm_hour)
        if col["pump"][i] and col["plain"][i]:
            meta.add(t0 + F.HOLD_S, F.ran(p))
    return {"mint": mint, "T": T, "VS": VS, "VT": VT, "RS": RS, **col}


def day_of(file):
    return os.path.basename(file)[:10]


def load_day(file, force=False):
    """The pinned arrays for one day's file, built once per distinct sha256 of its bytes."""
    day = day_of(file)
    digest = sha(file)
    npz = os.path.join(RDIR, f"{day}.npz")
    meta = os.path.join(RDIR, f"{day}.json")
    pin = C.load_json(meta, {}) if os.path.exists(meta) else {}
    if not force and os.path.exists(npz) and pin.get("sha256") == digest:
        with np.load(npz, allow_pickle=True) as z:
            return {k: z[k] for k in z.files}, pin
    rec = build(file)
    os.makedirs(RDIR, exist_ok=True)
    np.savez_compressed(npz + ".tmp.npz", **rec)
    os.replace(npz + ".tmp.npz", npz)
    pin = {"day": day, "source": os.path.relpath(file, ROOT), "sha256": digest, "bytes": os.path.getsize(file), "launches": int(len(rec["mint"])),
           "built": C.iso()}
    C.save_json(meta, pin)
    return rec, pin


def concat(recs):
    out = {}
    for k in recs[0]:
        out[k] = np.concatenate([r[k] for r in recs])
    return out


def load(days=4, paths_dir=None):
    """The last `days` day files as one record, plus a day label per launch and the pins. RDIR is where the pins live; the runner
    points it at a tape's own folder (state/academy/record for the home tape, state/academy/vps/record for the VPS tape)."""
    files = sorted(glob.glob(os.path.join(paths_dir or os.path.join(C.ROOT, "journal", "paths"), "*.jsonl")))[-days:]
    recs, pins, labels = [], [], []
    for f in files:
        r, pin = load_day(f)
        if len(r["mint"]):
            recs.append(r); pins.append(pin); labels += [day_of(f)] * len(r["mint"])
    if not recs:
        return None, [], np.array([])
    return concat(recs), pins, np.array(labels)


def coverage_hours(rec, day_mask):
    """Hours of the day with at least one launch: the sensor's uptime as the tape shows it."""
    if not day_mask.any():
        return 0
    return int(len(set(rec["hour"][day_mask].astype(int))))
