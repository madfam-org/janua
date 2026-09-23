"""Guards for scripts/alembic_promote_guard.py — the check that stops a promote.

The guard's whole value is that it fails when it should. A guard that quietly
returns 0 on a drifted ledger is worse than no guard, because the green check
is then evidence of something nobody verified. So the tests here are mostly
about the failing directions: drift blocks, an unknown recorded revision counts
as maximum drift, a broken ledger is an error rather than a pass, and a
non-linear chain refuses to guess.

Everything is `ast` + JSON, so none of it needs a database, settings or the app
package — matching test_alembic_revision_graph.py, and for the same reason: a
guard that can be turned into a skip by an unimportable environment is not a
guard.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = API_ROOT / "scripts" / "alembic_promote_guard.py"
LEDGER_PATH = API_ROOT / "alembic" / "PROD_ALEMBIC_STATE.json"
VERSIONS_DIR = API_ROOT / "alembic" / "versions"


def _load_script():
    spec = importlib.util.spec_from_file_location("alembic_promote_guard", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["alembic_promote_guard"] = module
    spec.loader.exec_module(module)
    return module


guard = _load_script()


# ---------------------------------------------------------------------------
# The real repository state
# ---------------------------------------------------------------------------


def test_the_repo_chain_is_linear_and_ends_at_the_expected_head() -> None:
    """A branch would make "how many revisions ahead" ambiguous."""
    order = guard.linear_history(guard.load_graph())
    assert order[0] == "000"
    assert order[-1] == "018_email_events"
    assert len(order) == len(set(order))


def test_the_ledger_parses_and_declares_a_real_revision() -> None:
    """A ledger naming a revision this repo has never heard of is a typo, not drift."""
    ledger = guard.load_ledger()
    order = guard.linear_history(guard.load_graph())
    recorded = ledger["recorded_revision"]
    assert recorded in order, (
        f"PROD_ALEMBIC_STATE.json records {recorded!r}, which is not in the migration "
        "chain. Fix the ledger — as written the guard reads it as maximum drift."
    )
    assert ledger.get("verified_at"), "the ledger must say when it was last verified"


def test_the_ledger_is_valid_json_with_no_trailing_junk() -> None:
    json.loads(LEDGER_PATH.read_text())


# ---------------------------------------------------------------------------
# Drift arithmetic
# ---------------------------------------------------------------------------

ORDER = ["000", "001", "002", "003"]


def test_drift_is_zero_at_head() -> None:
    assert guard.drift(ORDER, "003") == 0


def test_drift_counts_revisions_between_recorded_and_head() -> None:
    assert guard.drift(ORDER, "001") == 2


def test_unknown_recorded_revision_is_maximum_drift() -> None:
    """ "Production says something we've never heard of" means we know nothing.

    Reading it as zero drift would let a corrupted or hand-edited ledger wave
    every promote through, which is the one outcome the guard must not allow.
    """
    assert guard.drift(ORDER, "not-a-revision") == len(ORDER)
    assert guard.drift(ORDER, None) == len(ORDER)


# ---------------------------------------------------------------------------
# Chain validation
# ---------------------------------------------------------------------------


def test_linear_history_rejects_a_branch() -> None:
    with pytest.raises(ValueError, match="multiple children"):
        guard.linear_history({"a": None, "b": "a", "c": "a"})


def test_linear_history_rejects_two_roots() -> None:
    with pytest.raises(ValueError, match="one root"):
        guard.linear_history({"a": None, "b": None})


def test_linear_history_rejects_an_orphan() -> None:
    """A revision no walk from the root reaches is silently un-promotable."""
    with pytest.raises(ValueError, match="unreachable"):
        guard.linear_history({"a": None, "b": "a", "z": "missing-parent"})


# ---------------------------------------------------------------------------
# Exit codes — what the workflow actually keys off
# ---------------------------------------------------------------------------


def _run(monkeypatch, tmp_path, recorded, argv) -> int:
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps({"recorded_revision": recorded, "verified_at": "2026-09-03"}))
    monkeypatch.setattr(guard, "LEDGER_PATH", ledger)
    return guard.main(argv)


def test_blocks_when_the_ledger_is_behind(monkeypatch, tmp_path, capsys) -> None:
    assert _run(monkeypatch, tmp_path, "011_invitation_columns", []) == guard.EXIT_BLOCKED
    out = capsys.readouterr()
    assert "018_email_events" in out.out
    assert "alembic_converge.py --check" in (out.out + out.err)


def test_passes_when_acknowledged(monkeypatch, tmp_path) -> None:
    assert (
        _run(monkeypatch, tmp_path, "011_invitation_columns", ["--acknowledged"]) == guard.EXIT_OK
    )


def test_passes_when_the_ledger_is_at_head(monkeypatch, tmp_path) -> None:
    assert _run(monkeypatch, tmp_path, "018_email_events", []) == guard.EXIT_OK


def test_max_drift_widens_the_tolerance(monkeypatch, tmp_path) -> None:
    assert (
        _run(monkeypatch, tmp_path, "017_payment_mail_dispatch", ["--max-drift", "1"])
        == guard.EXIT_OK
    )
    assert (
        _run(monkeypatch, tmp_path, "016_org_member_app_roles", ["--max-drift", "1"])
        == guard.EXIT_BLOCKED
    )


def test_a_broken_ledger_is_an_error_not_a_pass(monkeypatch, tmp_path) -> None:
    """Unreadable must never be mistaken for fine."""
    ledger = tmp_path / "ledger.json"
    ledger.write_text("{not json")
    monkeypatch.setattr(guard, "LEDGER_PATH", ledger)
    assert guard.main([]) == guard.EXIT_ERROR

    monkeypatch.setattr(guard, "LEDGER_PATH", tmp_path / "absent.json")
    assert guard.main([]) == guard.EXIT_ERROR


def test_github_format_emits_annotations(monkeypatch, tmp_path, capsys) -> None:
    _run(monkeypatch, tmp_path, "011_invitation_columns", ["--format", "github"])
    assert "::error::" in capsys.readouterr().out
