"""
Tests for data/eval/merge_questions.py.

tune on dev only; use test only for final numbers.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from data.eval.merge_questions import run as _run


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _write_q(path: Path, questions: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for q in questions:
            fh.write(json.dumps(q) + "\n")


def _make_q(qid: str, text: str = "", qtype: str = "definition") -> dict:
    return {
        "id": qid,
        "question": text or f"Question {qid}?",
        "answer": "Some answer.",
        "source_doc": "",
        "source_passage": "",
        "type": qtype,
    }


# ---------------------------------------------------------------------------
# fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_eval(tmp_path, monkeypatch):
    """Tiny eval directory: two files, one duplicate id and one duplicate text."""
    eval_dir = tmp_path / "data" / "eval"
    eval_dir.mkdir(parents=True)

    _write_q(eval_dir / "questions_p1.jsonl", [
        _make_q("t1-def-01"),
        _make_q("t1-unans-01", qtype="unanswerable"),
    ])
    _write_q(eval_dir / "questions_p2.jsonl", [
        _make_q("t2-def-01"),
        _make_q("t1-def-01"),                          # duplicate id – drop
        _make_q("t2-def-02", text="Question t1-def-01?"),  # duplicate text – drop
    ])

    # Patch validate and split subprocesses so tests run offline.
    monkeypatch.setattr(
        "data.eval.merge_questions._validate_file",
        lambda *_a, **_k: 0,
    )
    monkeypatch.setattr(
        "data.eval.merge_questions.subprocess.run",
        lambda *_a, **_k: type("R", (), {"returncode": 0})(),
    )

    return eval_dir


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

def test_merge_deduplicates_and_counts(tmp_eval, capsys):
    """Merged file drops duplicate id and duplicate text; final count is correct."""
    out_file = tmp_eval / "questions_all.jsonl"

    _run(data_eval_dir=tmp_eval, out_file=out_file)

    written = [
        json.loads(l)
        for l in out_file.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    ids = [q["id"] for q in written]

    # 5 raw questions; 2 dropped → 3 kept
    assert len(written) == 3, f"expected 3 after dedup, got {len(written)}"
    assert ids.count("t1-def-01") == 1, "duplicate id should appear exactly once"

    out = capsys.readouterr().out
    assert "WARN" in out, "should print a WARN for duplicates"


def test_merge_warns_below_100(tmp_eval, capsys):
    """Script warns when total question count is below 100."""
    out_file = tmp_eval / "questions_all.jsonl"

    _run(data_eval_dir=tmp_eval, out_file=out_file)

    out = capsys.readouterr().out
    assert "100" in out, "should warn about fewer than 100 questions"


def test_merge_exits_nonzero_on_validation_failure(tmp_eval, monkeypatch):
    """If any file fails validation, run() must sys.exit with non-zero."""
    monkeypatch.setattr(
        "data.eval.merge_questions._validate_file",
        lambda *_a, **_k: 1,
    )

    with pytest.raises(SystemExit) as exc_info:
        _run(data_eval_dir=tmp_eval, out_file=tmp_eval / "out.jsonl")

    assert exc_info.value.code != 0
