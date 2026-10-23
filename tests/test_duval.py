"""RI-04 engine arithmetic: curve fills pay impact and fees both ways; headline terms and name matching follow the contract."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import duval as D  # noqa: E402

FRESH = (30.0, 1.073e9)   # a pump.fun curve at creation: 30 virtual SOL, 1.073e9 virtual tokens


def test_round_trip_costs_fees_and_impact():
    vs, vt = FRESH
    tokens = D.buy(vs, vt, D.SIZE_SOL)
    assert 0 < tokens < vt
    k = vs * vt
    vs2 = vs + D.SIZE_SOL * (1 - D.PUMP_FEE) - D.TX_FEE_SOL
    back = D.sell(vs2, k / vs2, tokens)
    assert 0.96 * D.SIZE_SOL < back < 0.99 * D.SIZE_SOL     # about -2 %: 1 % fee each side plus the book's own impact


def test_sell_never_negative():
    assert D.sell(30.0, 1.073e9, 1.0) == 0.0


def test_terms_drop_outlets_and_generic_words():
    t = D._terms("Dow tumbles more than 800 points as Middle East tensions rise: Live updates - CNBC")
    assert "cnbc" not in t and "live" not in t and "middle" not in t and "east" not in t
    assert "middle east" in t
    t = D._terms("Trump says Starlink access restored, but Ukraine reports more interruptions - The Washington Post")
    assert t == {"trump", "starlink", "ukraine"}


def test_match_whole_words_symbol_and_pairs():
    terms = {"spacex": [], "middle east": [], "trump": [], "starlink": []}
    assert D.match("Tesla SpaceX", "TESTES", terms) == ["spacex"]
    assert D.match("Middle East Tensions", "MET", terms) == ["middle east"]
    assert D.match("croc dog", "crocdog", terms) == []
    assert D.match("Trumpcoin", "TRUMP", terms) == ["trump"]        # symbol equals the term
    assert D.match("Starlinkdown", "SLD", terms) == ["starlink"]     # 6+ letter term inside the squashed name


def test_decode_curve_layout():
    import base64
    import struct
    raw = bytes(8) + struct.pack("<QQQQQ", 1_073_000_000_000_000, 30_000_000_000, 793_100_000_000_000, 0, 1_000_000_000_000_000) + b"\x01" + bytes(100)
    c = D.decode_curve(base64.b64encode(raw).decode())
    assert c["v_tok"] == 1.073e9 and c["v_sol"] == 30.0 and c["supply"] == 1e9 and c["complete"] is True
