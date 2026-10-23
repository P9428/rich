"""The population replays a launch path with the engine's own curve arithmetic; exits fire in the contract's order."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ops"))
import duval as D        # noqa: E402
import population as P   # noqa: E402

V0 = [30.0, 1.073e9]
K = V0[0] * V0[1]


def curve_after(sol_in):
    vs = V0[0] + sol_in
    return [round(vs, 4), int(K / vs), round(sol_in, 4)]


def path(marks, match=("trump",), mint="Abc" + "pump", mcap=3000):
    return {"ts": "2026-10-24T00:00:00Z", "mint": mint, "name": "x", "sym": "X", "v0": V0, "init_sol": 0, "pool": "pump", "mayhem": False,
            "match": list(match), "mcap0_usd": mcap, "complete": None, "marks": [[t] + curve_after(s) for t, s in marks]}


def test_take_fires_when_buyers_arrive():
    tr = P.replay(path([(2, 0.0), (4, 5.0), (6, 12.0), (8, 20.0)]), P.CONTROL)
    assert tr and tr["why"] == "take" and tr["pct"] >= D.TAKE


def test_time_exit_on_a_flat_curve_pays_fees_only():
    tr = P.replay(path([(t, 0.0) for t in range(2, 70, 2)]), P.CONTROL)
    assert tr and tr["why"] == "time" and -0.04 < tr["pct"] < 0


def test_filters():
    p = path([(2, 0.0), (62, 0.0)])
    assert P.replay({**p, "match": []}, P.CONTROL) is None
    assert P.replay({**p, "match": []}, P.rule_of({"filter": "all"})) is not None
    assert P.replay({**p, "mint": "Abc"}, P.CONTROL) is None
    assert P.replay({**p, "mcap0_usd": 12_000}, P.CONTROL) is None


def test_first_buyer_entry_waits_for_real_sol():
    p = path([(2, 0.0), (4, 0.0), (6, 1.0), (8, 1.0), (62, 1.0)])
    tr = P.replay(p, P.rule_of({"first_buyer": True}))
    assert tr and tr["t_in"] == 6
    assert P.replay(path([(t, 0.0) for t in range(2, 70, 2)]), P.rule_of({"first_buyer": True})) is None


def test_book_constraint_caps_open_positions():
    ps = [dict(path([(2, 0.0), (62, 0.0)]), ts=f"2026-10-24T00:00:0{i}Z") for i in range(5)]
    assert len(P.book_constrained(ps, P.CONTROL, max_open=3)) == 3
