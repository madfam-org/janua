"""Which tests need CI's real PostgreSQL service, decided by evidence.

The suite runs in two CI jobs (.github/workflows/tests.yml): "API Tests
(Python)" runs everything except the tests marked ``database``, and "API
Tests (PostgreSQL)" runs exactly the tests marked ``database`` against its own
PostgreSQL service. Every test must land in exactly one of them.

A test *requires PostgreSQL* when the test function, or any fixture it uses
(directly or through other fixtures), reads one of the service URL variables in
``POSTGRES_URL_ENV_VARS`` -- either as a string literal or through a module
constant or helper function defined in the test tree. Only the PostgreSQL job
sets those variables, so a test that needs one but is not marked would run in
the main job, where it cannot reach a server.

``check_marker_matches_requirement`` enforces ``marker == requirement`` for
every collected test; tests/unit/conftest.py calls it at collection time, so a
mismatch stops the run in both jobs and locally.
"""

from __future__ import annotations

import inspect
import types
from pathlib import Path
from typing import Iterable

import pytest

MARKER = "database"

# The variables CI's PostgreSQL job points at its service. pytest.ini pins
# DATABASE_URL to sqlite for every run, so these are the only way a test
# reaches a real server.
POSTGRES_URL_ENV_VARS = frozenset(
    {
        "MIGRATION_TEST_DATABASE_URL",
        "JANUA_MAIL_TEST_DATABASE_URL",
        "AUDIT_TEST_DATABASE_URL",
    }
)

TESTS_ROOT = Path(__file__).resolve().parent

# Helpers are followed at most this many calls deep from a test or fixture.
_MAX_DEPTH = 4


def _code_objects(code: types.CodeType) -> Iterable[types.CodeType]:
    yield code
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            yield from _code_objects(const)


def _defined_in_tests(func: types.FunctionType) -> bool:
    try:
        return Path(func.__code__.co_filename).resolve().is_relative_to(TESTS_ROOT)
    except (OSError, ValueError):
        return False


def _reads_postgres_url(func: object, cache: dict[int, bool], depth: int = 0) -> bool:
    """True when ``func`` names a service URL variable, or calls a test-tree
    helper that does."""
    func = inspect.unwrap(func)  # type: ignore[arg-type]
    if not isinstance(func, types.FunctionType) or not _defined_in_tests(func):
        return False
    key = id(func.__code__)
    if key in cache:
        return cache[key]
    cache[key] = False  # breaks recursion cycles
    found = False
    for code in _code_objects(func.__code__):
        if any(isinstance(c, str) and c in POSTGRES_URL_ENV_VARS for c in code.co_consts):
            found = True
            break
        for name in code.co_names:
            value = func.__globals__.get(name)
            if isinstance(value, str) and value in POSTGRES_URL_ENV_VARS:
                found = True
            elif depth < _MAX_DEPTH and isinstance(value, types.FunctionType):
                found = _reads_postgres_url(value, cache, depth + 1)
            if found:
                break
        if found:
            break
    cache[key] = found
    return found


def requires_postgres(item: pytest.Item, cache: dict[int, bool] | None = None) -> bool:
    cache = {} if cache is None else cache
    funcs: list[object] = []
    if isinstance(item, pytest.Function):
        funcs.append(item.function)
        fixtureinfo = getattr(item, "_fixtureinfo", None)
        if fixtureinfo is not None:
            for name in fixtureinfo.names_closure:
                for fixturedef in fixtureinfo.name2fixturedefs.get(name, ()):
                    funcs.append(fixturedef.func)
    return any(_reads_postgres_url(func, cache) for func in funcs)


def check_marker_matches_requirement(items: Iterable[pytest.Item]) -> None:
    """Raise a usage error naming every test whose ``database`` marker and
    PostgreSQL requirement disagree."""
    cache: dict[int, bool] = {}
    unmarked: list[str] = []
    marked_without_need: list[str] = []
    for item in items:
        needs = requires_postgres(item, cache)
        marked = item.get_closest_marker(MARKER) is not None
        if needs and not marked:
            unmarked.append(item.nodeid)
        elif marked and not needs:
            marked_without_need.append(item.nodeid)
    if not (unmarked or marked_without_need):
        return
    lines = ["The PostgreSQL test split is out of sync (see tests/postgres_service.py)."]
    if unmarked:
        lines.append(
            f"These tests read a PostgreSQL service URL but are not marked "
            f"'{MARKER}', so CI would run them in the job without a server; "
            f"add @pytest.mark.{MARKER}:"
        )
        lines += [f"  {nodeid}" for nodeid in unmarked]
    if marked_without_need:
        lines.append(
            f"These tests are marked '{MARKER}' but read no PostgreSQL service URL "
            f"({', '.join(sorted(POSTGRES_URL_ENV_VARS))}); remove the marker, or "
            "add the variable they use to POSTGRES_URL_ENV_VARS and to the "
            "PostgreSQL job:"
        )
        lines += [f"  {nodeid}" for nodeid in marked_without_need]
    raise pytest.UsageError("\n".join(lines))
