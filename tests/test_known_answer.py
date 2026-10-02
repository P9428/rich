"""Known-answer pins from prereg/KNOWN_ANSWER.json: gate logic, paper exits (offline) and the resolver (live DexScreener)."""
import json
import os
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import paper as P      # noqa: E402
import resolve as R    # noqa: E402
import screen as S     # noqa: E402

KA = json.load(open(os.path.join(ROOT, "prereg", "KNOWN_ANSWER.json")))


@pytest.mark.parametrize("case", KA["screen"], ids=[c["name"] for c in KA["screen"]])
def test_gate(case):
    ok, why = S.gate({k: case[k] for k in ("liq", "age_min", "buys_h1", "sells_h1", "mc", "dev_create_sol")})
    assert ok == case["expect"], why


@pytest.mark.parametrize("case", KA["paper"], ids=[c["name"] for c in KA["paper"]])
def test_paper_exits(case):
    t0 = 1_000_000.0
    pos = P.Position("m", "SYM", case["marks"][0], t0, "ev")
    step = (case.get("hours", 1) * 3600) / max(1, len(case["marks"]) - 1)
    for i, m in enumerate(case["marks"]):
        pos.mark(m, t0 + i * step)
    assert pos.closed
    assert round(100 * pos.net_sol() / P.SIZE_SOL, 2) == case["expect_net_pct"]


def test_lone_capitalised_word_is_not_a_phrase():
    out = R.phrases("Why would the State of New York do this? Buy ANSEM.", set())
    names = [p for k, p in out if k == "name"]
    assert "State" not in names and "Why" not in names
    assert "New York" in names and "ANSEM" in names


def test_phrases_prefer_mints_and_tickers():
    out = R.phrases("Buy $SI now 9cRCn9rGT8V2imeM2BaKs13yhMEais3ruM3rPvTGpump Super Intelligence is here", {"The"})
    assert out[0] == ("mint", "9cRCn9rGT8V2imeM2BaKs13yhMEais3ruM3rPvTGpump")
    assert ("ticker", "SI") in out
    assert ("name", "Super Intelligence") in out


@pytest.mark.live
@pytest.mark.parametrize("case", KA["resolver"], ids=[c["expect_symbol"] for c in KA["resolver"]])
def test_resolver_live(case):
    accepted, near = R.resolve(case["text"], time.time(), ["The", "Artificial Intelligence"])
    assert any(a["symbol"].upper() == case["expect_symbol"].upper() for a in accepted), (accepted, near)
