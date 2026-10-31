"""The academy: the arena agrees with the population's replay on a hand-built path, the look-ahead rule refuses unknown keys, the ladder
climbs and kills by its rules, and the answer term moves the right way."""
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from academy import answer as AN, arena as A, cells as CE, record as R, rungs as RU, residual as RS, search as S   # noqa: E402

V0 = [30.0, 1.073e9]
K = V0[0] * V0[1]


def rec_of(paths):
    """A tiny record from (marks, match, init_sol) tuples; marks are (t, sol_in) pairs on a fresh curve."""
    n = len(paths)
    cols = {k: np.zeros(n) for k in R.COLS}
    T, VS, VT, RS_ = (np.full((n, R.M), np.nan) for _ in range(4))
    mint = np.empty(n, dtype=object)
    for i, (marks, match, init) in enumerate(paths):
        for j, (t, s) in enumerate(marks):
            vs = V0[0] + s
            T[i, j], VS[i, j], VT[i, j], RS_[i, j] = t, vs, K / vs, s
        mint[i] = f"mint{i}pump"
        cols["ts"][i] = 1_700_000_000 + i
        cols["match"][i] = match; cols["pump"][i] = 1; cols["plain"][i] = 1; cols["mcap0"][i] = 3000
        cols["init"][i] = init; cols["v0s"][i], cols["v0t"][i] = V0; cols["hour"][i] = 12
        cols["fam"][i] = R.family(init, marks[0][1])
    return {"mint": mint, "T": T, "VS": VS, "VT": VT, "RS": RS_, **cols}


def test_take_fires_when_buyers_arrive():
    rec = rec_of([([(1, 0.0), (3, 5.0), (5, 12.0), (7, 20.0)], 1, 0)])
    s = A.score(rec, CE.make("c"))
    assert A.WHY[int(s["why"][0])] == "take" and s["pct"][0] >= 0.20


def test_flat_curve_pays_fees_only_and_times_out():
    rec = rec_of([([(t, 0.0) for t in range(1, 70, 2)], 1, 0)])
    s = A.score(rec, CE.make("c"))
    assert A.WHY[int(s["why"][0])] == "time" and -0.04 < s["pct"][0] < 0


def test_stop_books_what_the_mark_says():
    # a dump between two marks: the stop books the mark below the stop, as the live book does
    rec = rec_of([([(1, 0.0), (3, 2.0), (5, -10.0)], 1, 0)])
    s = A.score(rec, CE.make("c"))
    assert A.WHY[int(s["why"][0])] == "stop" and s["pct"][0] < -0.05


def test_universe_and_entry_keys():
    rec = rec_of([([(1, 0.0), (61, 0.0)], 0, 0), ([(1, 0.0), (61, 0.0)], 2, 3.0)])
    assert np.isnan(A.score(rec, CE.make("c"))["net"][0])                                   # unmatched: the control skips it
    assert np.isfinite(A.score(rec, CE.make("c", {"filter": "all"}))["net"][0])
    assert np.isnan(A.score(rec, CE.make("c", {"init_max": 0.0}))["net"][1])                 # the creator bought 3 SOL
    assert np.isfinite(A.score(rec, CE.make("c", {"fam": ["bundled"]}))["net"][1])
    assert np.isnan(A.score(rec, CE.make("c", None, {"rsol_min": 1.0}))["net"][1])            # nobody outside bought at the entry mark


def test_wait_buy_enters_at_the_first_outside_buy():
    rec = rec_of([([(1, 0.0), (3, 0.0), (5, 1.0), (7, 1.0), (61, 1.0)], 1, 0)])
    s = A.score(rec, CE.make("c", None, {"wait_buy": True}))
    assert s["ei"][0] == 2
    rec = rec_of([([(t, 0.0) for t in range(1, 70, 2)], 1, 0)])
    assert A.score(rec, CE.make("c", None, {"wait_buy": True}))["ei"][0] == -1


def test_trail_exits_below_the_peak():
    rec = rec_of([([(1, 0.0), (3, 3.0), (5, 6.0), (7, 2.0), (61, 2.0)], 1, 0)])
    s = A.score(rec, CE.make("c", None, None, {"take": 1.0, "stop": -0.5, "trail": 0.05}))
    assert A.WHY[int(s["why"][0])] == "trail"


def test_look_ahead_rule_refuses_unknown_keys():
    try:
        CE.validate({"universe": {"peak_pct": 0.5}, "entry": {}, "exit": {"take": 0.2, "stop": -0.05, "hold": 60}, "size": 1})
    except ValueError as e:
        assert "not known at the entry mark" in str(e)
    else:
        raise AssertionError("a key that is only known after the entry was accepted")


def test_cell_id_is_stable_and_mutation_moves_one_key():
    c = CE.make("c")
    assert c["id"] == CE.make("other name")["id"]
    rnd = random.Random(1)
    m = CE.mutate(c, rnd)
    diffs = sum(1 for part in ("universe", "entry", "exit") for k in c[part] if c[part][k] != m[part][k])
    assert 1 <= diffs <= 3 and m["parent"] == c["id"]


def test_ladder_climbs_on_a_good_group_and_kills_on_a_bad_one():
    st = RU.promote({}, "abc", "2026-10-29-test")
    good = [{"ts": "t", "mint": f"m{i}", "size": 0.01, "real": 0.001, "pred": 0.0011, "resid": -0.0001} for i in range(RU.GROUP)]
    st = RU.update(st, "abc", good)
    assert st["abc"]["rung"] == 1 and st["abc"]["status"] == "rung"
    bad = [{"ts": "t", "mint": f"m{i}", "size": 0.03, "real": -0.003, "pred": -0.0029, "resid": -0.0001} for i in range(RU.GROUP)]
    st = RU.update(st, "abc", bad)
    assert st["abc"]["status"] == "killed" and "UCB" in st["abc"]["history"][-1]["what"]


def test_ladder_kills_when_the_simulator_is_wrong():
    st = RU.promote({}, "abc", "2026-10-29-test")
    legs = [{"ts": "t", "mint": f"m{i}", "size": 0.01, "real": 0.0005, "pred": 0.003, "resid": -0.0025} for i in range(RU.GROUP)]
    st = RU.update(st, "abc", legs)
    assert st["abc"]["status"] == "killed" and "simulator" in st["abc"]["history"][-1]["what"]


def test_eligibility_needs_fit_held_and_the_answer():
    row = {"fit": {"n": 200, "mean": 0.01}, "held": {"n": 40, "mean": 0.01}, "held_lb": 0.002, "answered": 0.005}
    assert RU.eligible(row)[0]
    assert not RU.eligible({**row, "held_lb": -0.001})[0]
    assert not RU.eligible({**row, "answered": -0.001})[0]
    assert not RU.eligible({**row, "fit": {"n": 50, "mean": 0.01}})[0]


def test_answer_term_moves_with_our_own_fills():
    pri = {name: {"n": 100, "slip": 0.0, "p": 0.0} for name in R.FAMILIES}
    fills = [{"fam": 1, "sell_vs_mark": -0.20}] * 5
    post = AN.posterior(pri, fills)
    assert post["sniped"]["slip"] < -0.05 and post["sniped"]["p"] > 0.2 and post["empty"]["slip"] == 0.0


def test_residual_pairs_a_leg_with_its_launch():
    rec = rec_of([([(t, 0.0) for t in range(1, 70, 2)], 1, 0)])
    fills = [{"ts": "t", "mint": "mint0pump", "fam": 0, "size": 0.01, "net": -0.0014, "exit": "time"}, {"ts": "t", "mint": "nope", "fam": 0, "size": 0.01, "net": 0.0}]
    rows = RS.pair(rec, fills, {})
    assert rows[0]["pred"] is not None and abs(rows[0]["resid"]) < 0.001 and rows[1]["pred"] is None


def test_split_is_strictly_later():
    labels = np.array(["d1", "d1", "d2", "d3"])
    fit, held, fit_days, held_day = S.split(labels)
    assert held_day == "d3" and fit_days == ["d1", "d2"] and held.sum() == 1 and fit.sum() == 3


def _ops_academy():
    import importlib.util
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ops", "academy.py")
    spec = importlib.util.spec_from_file_location("ops_academy", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_round_is_due_when_the_window_slides():
    """10-31: the record shrank by a day (10-26 left the window) and 'grew by -14596' blocked every round; a shrunk record is a new fit."""
    OPS = _ops_academy()
    fire, grown = OPS.due(38839, {"launches_at_round": 53435}, {"c": 1})
    assert fire and grown == 38839
    fire, grown = OPS.due(100, {"launches_at_round": 80}, {"c": 1})
    assert not fire and grown == 20
    assert OPS.due(80 + S.PACE, {"launches_at_round": 80}, {"c": 1})[0]
    assert OPS.due(10, {"launches_at_round": 10}, {})[0]          # an empty roster always scores
    assert OPS.due(10, {"launches_at_round": 10}, {"c": 1}, force=True)[0]


def test_second_loop_is_refused_the_lock(tmp_path):
    OPS = _ops_academy()
    lock = str(tmp_path / "academy.lock")
    first = OPS.single_instance(lock)
    assert first is not None
    assert OPS.single_instance(lock) is None
    first.close()
    assert OPS.single_instance(lock) is not None
