"""The PostgreSQL test split stays exact.

CI runs the API suite in two parallel jobs (.github/workflows/tests.yml): the
tests marked ``database`` in "API Tests (PostgreSQL)", which has the server,
and everything else in "API Tests (Python)". tests/postgres_service.py checks
at collection time that the marker matches what each test reads; these tests
guard the inputs that check relies on, and scripts/check-api-test-split.sh
proves the two job selections partition the suite.
"""

from __future__ import annotations

import re
import types
from pathlib import Path

import pytest
import yaml

from tests import postgres_service
from tests.postgres_service import MARKER, POSTGRES_URL_ENV_VARS, TESTS_ROOT

REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "tests.yml"

# Any variable shaped like the service URLs, e.g. <SOMETHING>_TEST_DATABASE_URL.
URL_VARIABLE_SHAPE = re.compile(r"\b[A-Z][A-Z0-9_]*_TEST_DATABASE_URL\b")


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())


def _step_env_keys(job: dict) -> set[str]:
    keys = set(job.get("env") or {})
    for step in job.get("steps", []):
        keys |= set(step.get("env") or {})
    return keys


def _pytest_step(job: dict) -> dict:
    steps = [s for s in job["steps"] if "pytest" in str(s.get("run", ""))]
    assert len(steps) == 1, [s.get("name") for s in steps]
    return steps[0]


def test_every_service_url_variable_in_the_suite_is_known() -> None:
    """A new *_TEST_DATABASE_URL must join POSTGRES_URL_ENV_VARS (and the
    PostgreSQL job), or the collection check could not see its tests."""
    seen: dict[str, set[str]] = {}
    for path in (TESTS_ROOT / "unit").rglob("*.py"):
        for name in URL_VARIABLE_SHAPE.findall(path.read_text(encoding="utf-8")):
            seen.setdefault(name, set()).add(str(path.relative_to(TESTS_ROOT)))
    unknown = {name: files for name, files in seen.items() if name not in POSTGRES_URL_ENV_VARS}
    assert not unknown, unknown
    assert set(seen) == set(POSTGRES_URL_ENV_VARS), "a listed variable is no longer used"


def test_only_the_postgres_job_gets_the_service_urls() -> None:
    jobs = _workflow()["jobs"]
    postgres_env = set(_pytest_step(jobs["api-postgres-tests"]).get("env") or {})
    assert POSTGRES_URL_ENV_VARS <= postgres_env
    assert "postgres" in jobs["api-postgres-tests"]["services"]

    # Without the URLs, an unmarked PostgreSQL test fails in api-tests
    # instead of passing without a server.
    assert not POSTGRES_URL_ENV_VARS & _step_env_keys(jobs["api-tests"])
    assert "postgres" not in (jobs["api-tests"].get("services") or {})


def test_the_jobs_select_by_the_shared_marker_expressions() -> None:
    workflow = _workflow()
    env, jobs = workflow["env"], workflow["jobs"]
    assert env["API_TESTS_MARKERS"] == f"{env['API_ALL_TESTS_MARKERS']} and not {MARKER}"
    assert env["API_POSTGRES_TESTS_MARKERS"] == f"{MARKER} and {env['API_ALL_TESTS_MARKERS']}"
    assert '-m "$API_TESTS_MARKERS"' in _pytest_step(jobs["api-tests"])["run"]
    assert '-m "$API_POSTGRES_TESTS_MARKERS"' in _pytest_step(jobs["api-postgres-tests"])["run"]
    split_steps = [
        s
        for s in jobs["api-postgres-tests"]["steps"]
        if "check-api-test-split.sh" in str(s.get("run"))
    ]
    assert len(split_steps) == 1


def _synthetic(source: str) -> dict[str, types.FunctionType]:
    """Functions compiled as if they lived in the test tree, so the detector
    follows them; the variable names are assembled at runtime so this module
    itself reads none."""
    namespace: dict[str, object] = {}
    exec(compile(source, str(TESTS_ROOT / "unit" / "synthetic_module.py"), "exec"), namespace)
    return {k: v for k, v in namespace.items() if isinstance(v, types.FunctionType)}


def test_detection_follows_literals_constants_and_helpers() -> None:
    known = sorted(POSTGRES_URL_ENV_VARS)[0]
    funcs = _synthetic(
        "import os\n"
        f"URL_VAR = {known!r}\n"
        f"def by_literal():\n    return os.environ.get({known!r})\n"
        "def by_constant():\n    return os.environ.get(URL_VAR)\n"
        "def helper():\n    return by_constant()\n"
        "def by_helper():\n    return helper()\n"
        "def by_nested():\n    def inner():\n        return by_literal()\n    return inner\n"
        "def unrelated():\n    return os.environ.get('DATABASE_URL')\n"
    )
    cache: dict[int, bool] = {}
    for name in ("by_literal", "by_constant", "by_helper", "by_nested"):
        assert postgres_service._reads_postgres_url(funcs[name], cache), name
    assert not postgres_service._reads_postgres_url(funcs["unrelated"], cache)


class _Item:
    """Just enough of a collected item for the check; not a pytest.Function,
    so it reads nothing."""

    def __init__(self, nodeid: str, marked: bool) -> None:
        self.nodeid = nodeid
        self._marked = marked

    def get_closest_marker(self, name: str):
        return object() if self._marked and name == MARKER else None


def test_a_marked_test_that_reads_no_service_url_is_reported() -> None:
    postgres_service.check_marker_matches_requirement([_Item("t::plain", marked=False)])
    with pytest.raises(pytest.UsageError, match="t::marked"):
        postgres_service.check_marker_matches_requirement([_Item("t::marked", marked=True)])
