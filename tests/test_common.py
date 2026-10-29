"""The loaders after a hard crash (ruled decisions/2026-10-29-checklist-tape-outage): a NUL-filled state file reads as missing and a
NUL or torn line in a journal is skipped, each logged once to monitor/journal-errors.log, so the engine and the journal come back on
their own instead of dying at startup until an operator repairs the files by hand (as on 2026-10-09..10-21 and 2026-10-28)."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import common as C  # noqa: E402


def _errors():
    f = C.path("monitor", "journal-errors.log")
    return [json.loads(l) for l in open(f, encoding="utf-8")] if os.path.exists(f) else []


def test_nul_filled_state_file_reads_as_default(tmp_path):
    f = tmp_path / "heartbeat.json"
    f.write_bytes(b"\x00" * 250)
    assert C.load_json(str(f), {}) == {}
    assert C.load_json(str(f), []) == []
    assert any(e["where"] == "loader" and "NUL-filled" in e["err"] for e in _errors()[-2:])


def test_empty_state_file_reads_as_default(tmp_path):
    f = tmp_path / "positions.json"
    f.write_text("", encoding="utf-8")
    assert C.load_json(str(f), [1]) == [1]


def test_good_state_file_still_parses(tmp_path):
    f = tmp_path / "news.json"
    f.write_text(json.dumps({"a": 1}), encoding="utf-8")
    assert C.load_json(str(f), {}) == {"a": 1}


def test_bad_json_still_raises(tmp_path):
    f = tmp_path / "x.json"
    f.write_text("{not json", encoding="utf-8")
    try:
        C.load_json(str(f), {})
    except ValueError:
        return
    raise AssertionError("a malformed but non-empty file must still raise: that is not crash damage")


def test_jsonl_skips_nul_and_torn_lines(tmp_path):
    f = tmp_path / "launches.jsonl"
    rows = [{"ts": "2026-10-28T16:43:00Z", "n": 1}, {"ts": "2026-10-28T16:43:01Z", "n": 2}]
    f.write_text(json.dumps(rows[0]) + "\n" + "\x00" * 1134 + "\n" + '{"ts": "2026-10-28T16' + "\n" + "\n" + json.dumps(rows[1]) + "\n", encoding="utf-8")
    before = len(_errors())
    assert C.read_jsonl(str(f)) == rows
    errs = _errors()
    assert len(errs) == before + 1 and "skipped 2" in errs[-1]["err"] and "launches.jsonl" in errs[-1]["err"]


def test_clean_jsonl_logs_nothing(tmp_path):
    f = tmp_path / "clean.jsonl"
    f.write_text('{"a": 1}\n\n{"a": 2}\n', encoding="utf-8")
    before = len(_errors())
    assert C.read_jsonl(str(f)) == [{"a": 1}, {"a": 2}]
    assert len(_errors()) == before
