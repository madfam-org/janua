"""Every audit call site in ``app/`` matches the code it calls.

Audit calls fail only when they run, and most callers catch the failure, so a
call that names a missing event type, passes an argument ``log()`` does not
take, or reads an ``AuditLog`` column the model does not map goes unnoticed.
This test reads the source of ``app/`` and checks, for each module that imports
them from ``app.services.audit_logger`` / ``app.models``:

- ``AuditEventType.X`` / ``AuditAction.X``: ``X`` is a member;
- ``<audit logger>.log(...)``: every keyword is a parameter of
  ``AuditLogger.log`` and the required ones are passed;
- ``AuditLog(...)`` and ``AuditLog.X``: every keyword and attribute is mapped.

``KNOWN_UNMAPPED`` lists the ``AuditLog`` references that predate this test and
are still to be fixed. The test fails on any other one, and on an entry that no
longer occurs, so the list only shrinks.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Set, Tuple

from sqlalchemy import inspect as sa_inspect

from app.models import AuditLog
from app.services.audit_logger import AuditEventType, AuditLogger

APP_DIR = Path(__file__).resolve().parents[2] / "app"
AUDIT_MODULE = "app.services.audit_logger"
MODELS_MODULE = "app.models"

LOG_PARAMETERS = inspect.signature(AuditLogger.log).parameters
LOG_KEYWORDS = set(LOG_PARAMETERS) - {"self"}
LOG_REQUIRED = {
    name
    for name, parameter in LOG_PARAMETERS.items()
    if name != "self" and parameter.default is inspect.Parameter.empty
}
AUDIT_LOG_KEYWORDS = {attr.key for attr in sa_inspect(AuditLog).attrs}

# Path, then ``AuditLog.<attribute>`` or ``AuditLog(<keyword>=...)``.
KNOWN_UNMAPPED = {
    # AuthService.create_audit_log
    "app/services/auth_service.py AuditLog(event_data=...)",
    # RoleService audit rows
    "app/services/role_service.py AuditLog(organization_id=...)",
    # AuditService
    *(
        f"app/services/audit_service.py AuditLog({name}=...)"
        for name in (
            "organization_id",
            "actor_id",
            "actor_type",
            "actor_ip",
            "actor_user_agent",
            "old_values",
            "new_values",
            "metadata",
            "compliance_relevant",
            "compliance_standards",
            "risk_level",
            "is_suspicious",
            "success",
            "error_message",
        )
    ),
    *(
        f"app/services/audit_service.py AuditLog.{name}"
        for name in (
            "occurred_at",
            "organization_id",
            "actor_id",
            "risk_level",
            "compliance_relevant",
        )
    ),
    # GraphQL audit log query
    "app/graphql/schema.py AuditLog.timestamp",
}


def _module_name(path: Path) -> str:
    return ".".join(path.relative_to(APP_DIR.parent).with_suffix("").parts)


def _resolve(node: ast.ImportFrom, module: str, is_package: bool) -> Optional[str]:
    if node.level == 0:
        return node.module
    package = module.split(".") if is_package else module.split(".")[:-1]
    if node.level > 1:
        package = package[: -(node.level - 1)]
    return ".".join(package + ([node.module] if node.module else []))


def _imported_names(tree: ast.Module, path: Path) -> Dict[Tuple[str, str], Set[str]]:
    """Map (module, name) to the local names it is imported as in this file."""
    module = _module_name(path)
    names: Dict[Tuple[str, str], Set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            source = _resolve(node, module, path.name == "__init__.py")
            for alias in node.names:
                names.setdefault((source or "", alias.name), set()).add(alias.asname or alias.name)
    return names


def _sources() -> Iterator[Tuple[Path, ast.Module]]:
    for path in sorted(APP_DIR.rglob("*.py")):
        yield path, ast.parse(path.read_text(), filename=str(path))


def _where(path: Path, node: ast.AST) -> str:
    return f"{path.relative_to(APP_DIR.parent)}:{node.lineno}"


def _is_audit_logger(receiver: ast.expr, logger_names: Set[str]) -> bool:
    """True for ``AuditLogger(...)`` and for names like ``audit_logger``."""
    if isinstance(receiver, ast.Call) and isinstance(receiver.func, ast.Name):
        return receiver.func.id in logger_names
    if isinstance(receiver, ast.Name):
        return "audit_logger" in receiver.id
    if isinstance(receiver, ast.Attribute):
        return "audit_logger" in receiver.attr
    return False


def test_event_types_exist():
    members = set(AuditEventType.__members__)
    problems: List[str] = []
    for path, tree in _sources():
        imported = _imported_names(tree, path)
        enums = imported.get((AUDIT_MODULE, "AuditEventType"), set()) | imported.get(
            (AUDIT_MODULE, "AuditAction"), set()
        )
        if _module_name(path) == AUDIT_MODULE:
            enums |= {"AuditEventType", "AuditAction"}
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id in enums
                and not node.attr.startswith("_")
                and node.attr not in members
                and not hasattr(AuditEventType, node.attr)
            ):
                problems.append(f"{_where(path, node)} {node.value.id}.{node.attr}")
    assert problems == []


def test_log_calls_match_the_signature():
    problems: List[str] = []
    for path, tree in _sources():
        imported = _imported_names(tree, path)
        logger_names = imported.get((AUDIT_MODULE, "AuditLogger"), set())
        if _module_name(path) == AUDIT_MODULE:
            logger_names = logger_names | {"AuditLogger"}
        if not logger_names:
            continue
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("log", "log_event")
                and _is_audit_logger(node.func.value, logger_names)
            ):
                continue
            if node.func.attr == "log_event":
                problems.append(f"{_where(path, node)} AuditLogger has no log_event()")
                continue
            if node.args or any(k.arg is None for k in node.keywords):
                continue  # positional or **kwargs: not checked statically
            given = {k.arg for k in node.keywords}
            for name in sorted(given - LOG_KEYWORDS):
                problems.append(f"{_where(path, node)} log() takes no {name!r}")
            for name in sorted(LOG_REQUIRED - given):
                problems.append(f"{_where(path, node)} log() needs {name!r}")
    assert problems == []


def test_audit_log_attributes_are_mapped():
    problems: Set[str] = set()
    for path, tree in _sources():
        names = _imported_names(tree, path).get((MODELS_MODULE, "AuditLog"), set())
        if not names:
            continue
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id in names
                and not hasattr(AuditLog, node.attr)
            ):
                problems.add(f"{_where(path, node).split(':')[0]} AuditLog.{node.attr}")
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in names
            ):
                for keyword in node.keywords:
                    if keyword.arg is not None and keyword.arg not in AUDIT_LOG_KEYWORDS:
                        problems.add(
                            f"{_where(path, node).split(':')[0]} AuditLog({keyword.arg}=...)"
                        )
    assert sorted(problems - KNOWN_UNMAPPED) == []
    assert sorted(KNOWN_UNMAPPED - problems) == [], "fixed: remove from KNOWN_UNMAPPED"


def test_the_checks_see_the_call_sites():
    """Guard against the checks above silently matching nothing."""
    logger_calls = 0
    audit_log_uses = 0
    for path, tree in _sources():
        imported = _imported_names(tree, path)
        logger_names = imported.get((AUDIT_MODULE, "AuditLogger"), set())
        if imported.get((MODELS_MODULE, "AuditLog")):
            audit_log_uses += 1
        for node in ast.walk(tree):
            if (
                logger_names
                and isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "log"
                and _is_audit_logger(node.func.value, logger_names)
            ):
                logger_calls += 1
    assert logger_calls >= 20
    assert audit_log_uses >= 3
