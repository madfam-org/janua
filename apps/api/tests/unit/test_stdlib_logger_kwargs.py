"""Stdlib loggers must never get structlog-style keyword fields.

WHY THIS TEST EXISTS. The API uses two kinds of logger side by side:
`structlog.get_logger()` (a BoundLogger: `logger.info("msg", key=value)` is
fine) and `logging.getLogger(__name__)` (a stdlib Logger). structlog's
configuration (`app/core/logging.py`, `app/logging/structured_logger.py`) only
shapes the loggers structlog hands out; a stdlib Logger keeps the stdlib
signature, and `Logger._log()` rejects any keyword other than `exc_info`,
`stack_info`, `stacklevel` and `extra`:

    TypeError: Logger._log() got an unexpected keyword argument 'key'

That turns "log and continue" into "crash": the exception handler raises
instead of returning, and a log line placed after `db.commit()` turns a request
that already succeeded into a 500. #162 ("parameterized logging") converted
f-strings into keyword fields on both kinds of logger, and the stdlib half has
been raising ever since (invitation acceptance with Redis down, every
`GET /integrations/{provider}/token`, webhook endpoint registration, ...).

The same handler also breaks if `extra` names a LogRecord attribute
(`message`, `name`, `args`, ...): `Logger.makeRecord()` raises
`KeyError: "Attempt to overwrite 'message' in LogRecord"`.

WHAT IS ASSERTED. Every module under `app/` is PARSED (not imported) and each
call `<logger>.<level>(...)` whose receiver provably is a stdlib logger is
checked. A receiver is a stdlib logger when it is bound, following Python's
scoping rules, only to `logging.getLogger(...)` / `logging.LoggerAdapter(...)`
or one of the project helpers that return one (`STDLIB_LOGGER_FACTORIES`),
including through `self.<attr>`, aliases and `from app.x import logger`. The
module-level `logging.info(...)` functions count too. Anything else (structlog
loggers, parameters, unresolved names) is skipped, so the guard cannot fail on
a structlog call; `test_guard_recognises_the_shapes_it_claims_to` pins both
halves.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import pytest

# apps/api/tests/unit/ -> apps/api
API_ROOT = Path(__file__).resolve().parents[2]
APP_DIR = API_ROOT / "app"

LOG_METHODS = frozenset(
    {"debug", "info", "warning", "warn", "error", "exception", "critical", "fatal", "log"}
)
STDLIB_LOG_KWARGS = frozenset({"exc_info", "stack_info", "stacklevel", "extra"})

#: `extra` keys that collide with LogRecord attributes (Logger.makeRecord raises
#: KeyError). `taskName` exists from Python 3.12; the image runs 3.14.
RESERVED_EXTRA_KEYS = frozenset(
    {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "asctime", "taskName",
    }
)  # fmt: skip

#: Callables that return a stdlib Logger (or LoggerAdapter, which forwards its
#: keyword arguments to Logger._log unchanged).
STDLIB_LOGGER_FACTORIES = frozenset(
    {
        "logging.getLogger",
        "logging.LoggerAdapter",
        "app.core.logger.get_logger",
        "app.core.logger.get_context_logger",
        "app.core.logger.LoggerAdapter",
        "app.utils.logger.get_logger",
    }
)

#: (path under app/, log message) of known hits fixed by another open change.
#: Empty: janua#718 (CacheService.delete) is on main.
PENDING_ELSEWHERE: frozenset[tuple[str, str]] = frozenset()


@dataclass
class _Scope:
    module: str
    is_pkg: bool
    parent: _Scope | None = None
    cls: ast.ClassDef | None = None
    #: name -> assigned values; None marks a binding we cannot evaluate.
    names: dict[str, list[ast.AST | None]] = field(default_factory=dict)
    imports: dict[str, str] = field(default_factory=dict)

    def bind(self, name: str, value: ast.AST | None) -> None:
        self.names.setdefault(name, []).append(value)


def _resolve_relative(scope: _Scope, level: int, target: str | None) -> str:
    parts = scope.module.split(".")
    if not scope.is_pkg:
        parts = parts[:-1]
    if level > 1:
        parts = parts[: len(parts) - (level - 1)]
    return ".".join(parts + ([target] if target else []))


def _own_statements(node: ast.AST):
    """Nodes of this scope, without descending into nested defs/classes/lambdas."""
    for child in ast.iter_child_nodes(node):
        yield child
        if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            yield from _own_statements(child)


def _collect_bindings(scope: _Scope, node: ast.AST) -> None:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        args = node.args
        for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg]:
            if arg is not None:
                scope.bind(arg.arg, None)
    for child in _own_statements(node):
        if isinstance(child, ast.Assign):
            for target in child.targets:
                if isinstance(target, ast.Name):
                    scope.bind(target.id, child.value)
                else:
                    for sub in ast.walk(target):
                        if isinstance(sub, ast.Name):
                            scope.bind(sub.id, None)
        elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
            scope.bind(child.target.id, child.value)
        elif isinstance(child, (ast.AugAssign, ast.For, ast.AsyncFor, ast.NamedExpr)):
            target = child.target
            for sub in ast.walk(target):
                if isinstance(sub, ast.Name):
                    scope.bind(sub.id, None)
        elif isinstance(child, ast.withitem) and child.optional_vars is not None:
            for sub in ast.walk(child.optional_vars):
                if isinstance(sub, ast.Name):
                    scope.bind(sub.id, None)
        elif isinstance(child, ast.ExceptHandler) and child.name:
            scope.bind(child.name, None)
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            scope.bind(child.name, None)
        elif isinstance(child, ast.Import):
            for alias in child.names:
                if alias.asname:
                    scope.imports[alias.asname] = alias.name
                else:
                    head = alias.name.split(".")[0]
                    scope.imports[head] = head
        elif isinstance(child, ast.ImportFrom):
            base = (
                _resolve_relative(scope, child.level, child.module) if child.level else child.module
            )
            for alias in child.names:
                scope.imports[alias.asname or alias.name] = f"{base}.{alias.name}"


class _Analyzer:
    def __init__(self, module: str, tree: ast.Module, is_pkg: bool, resolve_module=None):
        self.tree = tree
        self.module_scope = _Scope(module, is_pkg)
        _collect_bindings(self.module_scope, tree)
        self._resolve_module = resolve_module or (lambda name: None)

    # -- name resolution ------------------------------------------------
    def _lookup(self, name: str, scope: _Scope):
        """("values", [exprs], defining scope) | ("import", dotted) | None."""
        current = scope
        while current is not None:
            if name in current.imports:
                return ("import", current.imports[name])
            if name in current.names:
                return ("values", current.names[name], current)
            current = current.parent
        return None

    def _dotted(self, expr: ast.AST, scope: _Scope) -> str | None:
        parts = []
        while isinstance(expr, ast.Attribute):
            parts.append(expr.attr)
            expr = expr.value
        if not isinstance(expr, ast.Name):
            return None
        found = self._lookup(expr.id, scope)
        if found is None or found[0] != "import":
            return None
        return ".".join([found[1], *reversed(parts)])

    # -- kinds -------------------------------------------------------------
    def is_logging_module(self, expr: ast.AST, scope: _Scope) -> bool:
        return isinstance(expr, ast.Name) and self._dotted(expr, scope) == "logging"

    def is_stdlib_logger(self, expr: ast.AST | None, scope: _Scope, depth: int = 0) -> bool:
        if expr is None or depth > 20:
            return False
        if isinstance(expr, ast.Call):
            if isinstance(expr.func, ast.Attribute) and expr.func.attr == "getChild":
                return self.is_stdlib_logger(expr.func.value, scope, depth + 1)
            return self._dotted(expr.func, scope) in STDLIB_LOGGER_FACTORIES
        if isinstance(expr, ast.Name):
            found = self._lookup(expr.id, scope)
            if found is None:
                return False
            if found[0] == "import":
                return self._imported_is_stdlib(found[1], depth + 1)
            _, values, defining = found
            return bool(values) and all(
                self.is_stdlib_logger(v, defining, depth + 1) for v in values
            )
        if isinstance(expr, ast.Attribute):
            if (
                isinstance(expr.value, ast.Name)
                and expr.value.id in ("self", "cls")
                and self._enclosing_class(scope) is not None
            ):
                values = self._class_attr_values(self._enclosing_class(scope), expr.attr)
                return bool(values) and all(
                    self.is_stdlib_logger(v, s, depth + 1) for v, s in values
                )
            return self._dotted(expr, scope) == "logging.root"
        return False

    def _imported_is_stdlib(self, dotted: str, depth: int) -> bool:
        if dotted == "logging.root":
            return True
        module, _, name = dotted.rpartition(".")
        other = self._resolve_module(module)
        if other is None:
            return False
        return other.is_stdlib_logger(ast.Name(id=name), other.module_scope, depth)

    @staticmethod
    def _enclosing_class(scope: _Scope) -> ast.ClassDef | None:
        while scope is not None:
            if scope.cls is not None:
                return scope.cls
            scope = scope.parent
        return None

    def _class_attr_values(self, cls: ast.ClassDef, attr: str):
        values = []
        for node in cls.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == attr for t in node.targets
            ):
                values.append((node.value, self.module_scope))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_scope = _Scope(
                    self.module_scope.module, self.module_scope.is_pkg, parent=self.module_scope
                )
                _collect_bindings(method_scope, node)
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Assign):
                        for t in sub.targets:
                            if (
                                isinstance(t, ast.Attribute)
                                and t.attr == attr
                                and isinstance(t.value, ast.Name)
                                and t.value.id in ("self", "cls")
                            ):
                                values.append((sub.value, method_scope))
        return values

    # -- the check ---------------------------------------------------------
    def violations(self, rel_path: str) -> list[str]:
        found: list[str] = []
        self._walk(self.tree, self.module_scope, rel_path, found)
        return found

    def _walk(self, node: ast.AST, scope: _Scope, rel_path: str, found: list[str]) -> None:
        for child in _own_statements(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                inner = _Scope(scope.module, scope.is_pkg, parent=scope)
                _collect_bindings(inner, child)
                self._walk(child, inner, rel_path, found)
            elif isinstance(child, ast.ClassDef):
                # Methods do not see class-body names, only `self.<attr>`.
                class_scope = _Scope(scope.module, scope.is_pkg, parent=scope, cls=child)
                self._walk(child, class_scope, rel_path, found)
            elif (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and child.func.attr in LOG_METHODS
            ):
                receiver = child.func.value
                if self.is_logging_module(receiver, scope) or self.is_stdlib_logger(
                    receiver, scope
                ):
                    self._check_call(child, rel_path, found)

    @staticmethod
    def _check_call(call: ast.Call, rel_path: str, found: list[str]) -> None:
        message_arg = call.args[1:2] if call.func.attr == "log" else call.args[:1]
        message = (
            message_arg[0].value
            if message_arg
            and isinstance(message_arg[0], ast.Constant)
            and isinstance(message_arg[0].value, str)
            else None
        )
        if (rel_path, message) in PENDING_ELSEWHERE:
            return
        where = f"app/{rel_path}:{call.lineno} {ast.unparse(call.func)}"
        # `msg` (and `level` for .log) are ordinary parameters, legal by keyword.
        allowed = STDLIB_LOG_KWARGS | {"msg"} | ({"level"} if call.func.attr == "log" else set())
        for keyword in call.keywords:
            if keyword.arg is None:
                found.append(f"{where}: **{ast.unparse(keyword.value)} (pass fields via extra=)")
            elif keyword.arg not in allowed:
                found.append(f"{where}: keyword {keyword.arg!r} (pass fields via extra=)")
            elif keyword.arg == "extra" and isinstance(keyword.value, ast.Dict):
                for key in keyword.value.keys:
                    if isinstance(key, ast.Constant) and key.value in RESERVED_EXTRA_KEYS:
                        found.append(f"{where}: extra key {key.value!r} is a LogRecord attribute")


def _module_name(path: Path) -> tuple[str, bool]:
    parts = list(path.relative_to(API_ROOT).with_suffix("").parts)
    is_pkg = parts[-1] == "__init__"
    if is_pkg:
        parts = parts[:-1]
    return ".".join(parts), is_pkg


@cache
def _analyzer_for_module(module: str) -> _Analyzer | None:
    base = API_ROOT.joinpath(*module.split("."))
    for path in (base.with_suffix(".py"), base / "__init__.py"):
        if path.is_file():
            return _analyzer_for_path(path)
    return None


@cache
def _analyzer_for_path(path: Path) -> _Analyzer:
    module, is_pkg = _module_name(path)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return _Analyzer(module, tree, is_pkg, resolve_module=_analyzer_for_module)


def _violations_in_source(source: str, rel_path: str = "synthetic.py") -> list[str]:
    analyzer = _Analyzer("app.synthetic", ast.parse(source), is_pkg=False)
    return analyzer.violations(rel_path)


def _modules_using_stdlib_logging() -> list[Path]:
    """Files that import `logging` or a project helper; the rest cannot match."""
    markers = ("import logging", "from logging import", "app.core.logger", "app.utils.logger")
    return sorted(
        path
        for path in APP_DIR.rglob("*.py")
        if any(marker in path.read_text(encoding="utf-8") for marker in markers)
    )


MODULES = _modules_using_stdlib_logging()


def test_the_sweep_found_modules_to_check():
    assert MODULES, f"no module under {APP_DIR} imports logging; is APP_DIR right?"


@pytest.mark.parametrize("path", MODULES, ids=[str(p.relative_to(APP_DIR)) for p in MODULES])
def test_stdlib_logger_calls_pass_fields_through_extra(path: Path):
    violations = _analyzer_for_path(path).violations(str(path.relative_to(APP_DIR)))
    assert not violations, "stdlib logger called with structlog-style fields:\n" + "\n".join(
        violations
    )


STDLIB_HITS = {
    "module logger": (
        "import logging\n"
        "logger = logging.getLogger(__name__)\n"
        "logger.error('Cache delete error', key='k', error='e')\n"
    ),
    "aliased getLogger, in an except handler": (
        "from logging import getLogger\n"
        "log = getLogger(__name__)\n"
        "def f():\n"
        "    try:\n"
        "        pass\n"
        "    except Exception as e:\n"
        "        log.warning('failed', error=str(e))\n"
    ),
    "self attribute": (
        "import logging\n"
        "class Service:\n"
        "    def __init__(self):\n"
        "        self.logger = logging.getLogger(__name__)\n"
        "    def run(self):\n"
        "        self.logger.info('ran', user_id='u')\n"
    ),
    "logging module function": "import logging\nlogging.info('hello', user_id='u')\n",
    "project helper": (
        "from app.core.logger import get_logger\n"
        "logger = get_logger(__name__)\n"
        "logger.info('hello', provider='p')\n"
    ),
    "reserved extra key": (
        "import logging\n"
        "logger = logging.getLogger(__name__)\n"
        "logger.info('hello', extra={'message': 'm'})\n"
    ),
}

NOT_STDLIB = {
    "structlog logger": (
        "import structlog\n"
        "logger = structlog.get_logger()\n"
        "logger.info('hello', user_id='u')\n"
    ),
    "structlog rebound locally in a stdlib module": (
        "import logging\n"
        "import structlog\n"
        "logger = logging.getLogger(__name__)\n"
        "def f():\n"
        "    logger = structlog.get_logger()\n"
        "    logger.info('hello', user_id='u')\n"
    ),
    "parameter named logger": (
        "import logging\n"
        "logger = logging.getLogger(__name__)\n"
        "def f(logger):\n"
        "    logger.info('hello', user_id='u')\n"
    ),
    "stdlib keywords only": (
        "import logging\n"
        "logger = logging.getLogger(__name__)\n"
        "logger.error('x', exc_info=True, stack_info=False, stacklevel=2, extra={'k': 1})\n"
        "logger.log(logging.INFO, 'x', extra={'error': 'e'})\n"
    ),
    "logger imported from structlog setup": (
        "from app.core.logging import logger\nlogger.info('hello', user_id='u')\n"
    ),
}


@pytest.mark.parametrize("source", STDLIB_HITS.values(), ids=STDLIB_HITS.keys())
def test_guard_recognises_the_shapes_it_claims_to(source: str):
    assert len(_violations_in_source(source)) >= 1


@pytest.mark.parametrize("source", NOT_STDLIB.values(), ids=NOT_STDLIB.keys())
def test_guard_leaves_structlog_and_unknown_loggers_alone(source: str):
    assert _violations_in_source(source) == []
