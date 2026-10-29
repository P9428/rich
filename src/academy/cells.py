"""A cell is a whole strategy: universe, entry, exit, size, abstain. Every key is drawn from a fixed list of fields that are known at
the create or at the entry mark (the look-ahead rule: a key not in KNOWN is refused, never scored). The id is a hash of the cell's
own JSON, so the same cell has the same id in every round and on every machine.

universe   filter      matched | all | unmatched            the news match at create
           pump_only   bool                                  mint ends in 'pump'
           mcap_max    USD                                   at create
           cls         None | narrative                      five.classify at create
           gate        None | live                           five.Meta at create (the trailing hour's runner share)
           fam         None | list of family names           record.FAMILIES, read at the first mark
           hours       None | [lo, hi) UTC                   at create
           init_max    None | SOL                            creator's buy at create
           nmatch_min  int                                   matched terms at create
entry      delay       seconds after create; 0 is the first mark (where a signed buy lands, measured 2026-10-28)
           wait_buy    bool                                  the first mark inside 10 s showing an outside buy
           rsol_min    None | SOL                            outside SOL already on the curve at the entry mark
           rsol_max    None | SOL
           mom_min     None | fraction                       price at the entry mark over the create price, minus one
           up          bool                                  the entry mark is above the mark before it
exit       take, stop  fractions                             on the mark, the book's own SOL added back (duval.mark_value)
           hold        seconds after entry
           trail       None | fraction                       exit when the mark falls this far below its peak (peak above 0)
size       SOL
"""
import hashlib
import json

KNOWN = {"universe": {"filter", "pump_only", "mcap_max", "cls", "gate", "fam", "hours", "init_max", "nmatch_min"},
         "entry": {"delay", "wait_buy", "rsol_min", "rsol_max", "mom_min", "up"},
         "exit": {"take", "stop", "hold", "trail"}}

CONTROL = {"name": "control (RI-04 at the first mark)",
           "universe": {"filter": "matched", "pump_only": True, "mcap_max": 10_000, "cls": None, "gate": None, "fam": None, "hours": None,
                        "init_max": None, "nmatch_min": 1},
           "entry": {"delay": 0.0, "wait_buy": False, "rsol_min": None, "rsol_max": None, "mom_min": None, "up": False},
           "exit": {"take": 0.20, "stop": -0.05, "hold": 60, "trail": None},
           "size": 1.5}

GRID = {"universe": {"filter": ["matched", "all", "unmatched"], "mcap_max": [6_000, 10_000, 20_000, 50_000], "cls": [None, None, "narrative"],
                     "gate": [None, None, "live"],
                     "fam": [None, None, ["empty"], ["sniped"], ["seeded", "bundled"], ["empty", "sniped"]],
                     "hours": [None, None, None, [0, 8], [8, 16], [16, 24], [12, 22]], "init_max": [None, None, 0.0, 1.0, 2.0],
                     "nmatch_min": [1, 1, 2]},
        "entry": {"delay": [0.0, 0.0, 2.0, 4.0, 6.0, 10.0, 20.0, 30.0], "wait_buy": [False, False, False, True],
                  "rsol_min": [None, None, None, 0.5, 1.0, 2.0, 5.0], "rsol_max": [None, None, None, 0.0, 0.5],
                  "mom_min": [None, None, None, 0.02, 0.05, 0.10, 0.20], "up": [False, False, True]},
        "exit": {"take": [0.05, 0.08, 0.10, 0.15, 0.20, 0.30, 0.50, 1.0], "stop": [-0.03, -0.05, -0.08, -0.10, -0.15, -0.20, -0.30],
                 "hold": [10, 20, 30, 45, 60, 90, 120, 180], "trail": [None, None, None, 0.05, 0.10, 0.20]}}

FORKS = [  # RI-04's one-variable forks (ops/population.py) and RI-05's rules as forks, each one key away from the control
    ("all launches (no news)", "universe", "filter", "all"), ("unmatched only", "universe", "filter", "unmatched"),
    ("entry +2 s", "entry", "delay", 2.0), ("entry +10 s", "entry", "delay", 10.0), ("entry after first outside buy", "entry", "wait_buy", True),
    ("take +10 %", "exit", "take", 0.10), ("take +30 %", "exit", "take", 0.30), ("take +50 %", "exit", "take", 0.50),
    ("stop -3 %", "exit", "stop", -0.03), ("stop -8 %", "exit", "stop", -0.08), ("stop -10 %", "exit", "stop", -0.10), ("stop -20 %", "exit", "stop", -0.20),
    ("hold 30 s", "exit", "hold", 30), ("hold 120 s", "exit", "hold", 120), ("hold 180 s", "exit", "hold", 180),
    ("mcap < $6K", "universe", "mcap_max", 6_000), ("mcap < $20K", "universe", "mcap_max", 20_000), ("any mint", "universe", "pump_only", False),
    ("RI-05 L1 live meta hour", "universe", "gate", "live"), ("RI-05 L2 narrative only", "universe", "cls", "narrative"),
    ("trail 10 %", "exit", "trail", 0.10), ("first in: nobody bought yet", "entry", "rsol_max", 0.0), ("someone bought 1 SOL+", "entry", "rsol_min", 1.0),
    ("price already +5 %", "entry", "mom_min", 0.05), ("empty family only", "universe", "fam", ["empty"]), ("creator bought nothing", "universe", "init_max", 0.0),
]
PART_ARG = {"universe": "universe", "entry": "entry", "exit": "exit_"}


def validate(cell):
    for part, keys in KNOWN.items():
        bad = set(cell[part]) - keys
        if bad:
            raise ValueError(f"cell key(s) not known at the entry mark: {part}.{sorted(bad)}")
    if cell["exit"]["take"] <= 0 or cell["exit"]["stop"] >= 0 or cell["exit"]["hold"] <= 0 or cell["size"] <= 0:
        raise ValueError("exit or size out of range")
    return cell


def canon(cell):
    return {"universe": {k: cell["universe"].get(k) for k in sorted(KNOWN["universe"])},
            "entry": {k: cell["entry"].get(k) for k in sorted(KNOWN["entry"])},
            "exit": {k: cell["exit"].get(k) for k in sorted(KNOWN["exit"])}, "size": float(cell["size"])}


def cell_id(cell):
    return hashlib.sha256(json.dumps(canon(cell), sort_keys=True).encode()).hexdigest()[:10]


def make(name, universe=None, entry=None, exit_=None, size=None):
    c = {"name": name, "universe": {**CONTROL["universe"], **(universe or {})}, "entry": {**CONTROL["entry"], **(entry or {})},
         "exit": {**CONTROL["exit"], **(exit_ or {})}, "size": CONTROL["size"] if size is None else size}
    validate(c)
    c["id"] = cell_id(c)
    return c


def forks():
    out = [make(CONTROL["name"])]
    for name, part, key, val in FORKS:
        out.append(make(name, **{PART_ARG[part]: {key: val}}))
    return out


def _tidy(u):
    if u["filter"] != "matched":
        u["nmatch_min"] = 0
        u["cls"] = None
    return u


def random_cell(rnd, name=None):
    u, e, x = ({k: rnd.choice(v) for k, v in GRID[part].items()} for part in ("universe", "entry", "exit"))
    c = make(name or "random", _tidy(u), e, x)
    c["name"] = name or f"r-{c['id']}"
    return c


def mutate(cell, rnd):
    """One key moved to another value of the grid: the strategist's smallest step from a roster cell."""
    part = rnd.choice(["universe", "entry", "exit"])
    key = rnd.choice(sorted(GRID[part]))
    c = {"universe": dict(cell["universe"]), "entry": dict(cell["entry"]), "exit": dict(cell["exit"]), "size": cell["size"]}
    v = c[part][key]
    for _ in range(8):
        v = rnd.choice(GRID[part][key])
        if v != c[part][key]:
            c[part][key] = v
            break
    out = make("m", _tidy(c["universe"]), c["entry"], c["exit"], c["size"])
    out["name"] = f"m-{cell['id']} {part}.{key}={v}"
    out["parent"] = cell["id"]
    return out


def describe(cell):
    """The cell's difference from the control, as words."""
    d = []
    for part in ("universe", "entry", "exit"):
        for k, v in cell[part].items():
            if v != CONTROL[part].get(k):
                d.append(f"{k}={v}")
    if cell["size"] != CONTROL["size"]:
        d.append(f"size={cell['size']}")
    return ", ".join(d) or "the control"
