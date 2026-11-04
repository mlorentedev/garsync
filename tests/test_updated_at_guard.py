"""AC8 — a guard over `updated_at`, because a write today is an incremental decision tomorrow.

`updated_at` moves on every upsert, including the ones that changed nothing but the bookkeeping column.
That is the measured fact behind this spec (ADR-008 §5 and `tests/test_idempotency.py`: an identical
re-pull changes exactly `updated_at` and nothing else). So the moment a reader treats
`updated_at > last_run` as "what changed since the last run", every row is new on every run and the
incremental path silently becomes a full scan that *believes* it is incremental.

The guard is lexical and deliberately strict: **every occurrence of the name in `src/` must be a write**
— a `SET` clause, an insert column, a row dict key, a store, or a column declaration. Prose (docstrings
and comments) is exempt because it cannot execute; everything else is a violation, including a
`SELECT updated_at` that only meant to display it. A display is a decision one refactor away, and the
cheap fix then is to read the column — which is what this file exists to prevent.

The boundary of this criterion, stated rather than hidden: it guards `updated_at`. The CLI also takes an
incremental decision, from `MAX(date)` over the daily tables (`cli.py`, `_dates_to_sync`) — a
*record-value* cursor of exactly the kind SUB-002 rejects, but a different column and pre-existing
behaviour, filed as SYNC-002 #123 instead of silently widening this guard into a failure on code this
branch does not own.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path

import pytest

NAME = "updated_at"
SRC_ROOT = Path(__file__).resolve().parent.parent / "src"

#: A clause keyword to the left of the occurrence puts it in a predicate or a projection: the column is
#: being read. The window is bounded so that prose near an unrelated statement cannot be accused.
_READ_CLAUSE = re.compile(
    r"\b(where|on|and|or|having|when|qualify|select|returning|order\s+by|group\s+by)\b",
    re.IGNORECASE,
)
_WRITE_CLAUSE = re.compile(r"\b(set|insert\s+into|values|update)\b", re.IGNORECASE)
#: What may follow the column when it is a decision rather than an assignment. A single `=` is excluded:
#: `updated_at = strftime(...)` is the write, and `updated_at = ?` inside a predicate is caught by the
#: clause rule instead.
_COMPARISON = re.compile(
    r"^\s*(>=|<=|<>|!=|>|<|~|\blike\b|\bis\b|\bin\b|\bbetween\b)", re.IGNORECASE
)
_WINDOW = 140


class Finding:
    """One occurrence of the name that is not provably a write."""

    def __init__(self, path: Path, lineno: int, excerpt: str, why: str) -> None:
        self.path = path
        self.lineno = lineno
        self.excerpt = " ".join(excerpt.split())[:110]
        self.why = why

    def __str__(self) -> str:
        try:
            shown = self.path.relative_to(SRC_ROOT.parent)
        except ValueError:  # a synthetic source from the guard's own tests
            shown = Path("<source>")
        return f"{shown}:{self.lineno}: {self.why} | {self.excerpt}"


def _prose_lines(text: str) -> set[int]:
    """Lines inside docstrings and comments: prose cannot read a column.

    A docstring is a string *statement*; a comment is a token the parser never sees. Everything else that
    mentions the name is code or SQL that runs.
    """
    lines: set[int] = set()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            head = node.body[0] if getattr(node, "body", None) else None
            if isinstance(head, ast.Expr) and isinstance(head.value, ast.Constant):
                value = head.value
                if isinstance(value.value, str):
                    lines.update(range(value.lineno, (value.end_lineno or value.lineno) + 1))
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (
        tokenize.TokenError,
        IndentationError,
    ):  # pragma: no cover - unparsable files fail elsewhere
        return lines
    lines.update(tok.start[0] for tok in tokens if tok.type == tokenize.COMMENT)
    return lines


def _clause_kind(before: str) -> str | None:
    """`read`/`write` for the nearest clause keyword to the left of the occurrence, inside the window."""
    window = before[-_WINDOW:]
    hits = [(m.start(), m.group(0)) for m in _READ_CLAUSE.finditer(window)]
    hits += [(m.start(), m.group(0)) for m in _WRITE_CLAUSE.finditer(window)]
    if not hits:
        return None
    _, word = max(hits, key=lambda pair: pair[0])
    return "read" if _READ_CLAUSE.fullmatch(word.strip()) or _READ_CLAUSE.search(word) else "write"


def scan_source(text: str, path: Path | None = None) -> list[Finding]:
    """Every occurrence of `updated_at` that is not provably a write.

    Three rules, and a fail-closed default: a comparison follows it, a reading clause precedes it, or the
    name is loaded as a Python value. Anything else — the `SET` clause, an insert column list, a row dict
    key, a `sa.Column` declaration, prose — is allowed.

    This runs over raw text on purpose. The dangerous shapes live inside SQL strings, and a pass over
    string literals alone loses the clause the moment the statement is assembled from several literals.
    """
    target = path or Path(".") / "<source>"
    prose = _prose_lines(text)
    lines = text.splitlines()
    offsets = [sum(len(line) + 1 for line in lines[:i]) for i in range(len(lines))]
    findings: list[Finding] = []
    for index, line in enumerate(lines):
        if index + 1 in prose:
            continue
        for match in re.finditer(rf"\b{NAME}\b", line):
            at = offsets[index] + match.end()
            if _COMPARISON.match(text[at : at + 30]):
                findings.append(Finding(target, index + 1, line, "compared"))
            elif _clause_kind(text[:at]) == "read":
                findings.append(Finding(target, index + 1, line, "read by a clause to its left"))
    for lineno in _python_loads(ast.parse(text)):
        findings.append(Finding(target, lineno, lines[lineno - 1], "loaded as a Python value"))
    return findings


def _python_loads(tree: ast.AST) -> list[int]:
    """Occurrences outside strings that *load* the name — a read in Python rather than in SQL."""
    lines: list[int] = []
    for node in ast.walk(tree):
        loaded_name = (
            isinstance(node, ast.Name) and node.id == NAME and isinstance(node.ctx, ast.Load)
        )
        loaded_column = (
            isinstance(node, ast.Subscript)
            and isinstance(node.slice, ast.Constant)
            and node.slice.value == NAME
            and isinstance(node.ctx, ast.Load)
        )
        if loaded_name or loaded_column:
            lines.append(node.lineno)
    return sorted(set(lines))


def _sources() -> list[Path]:
    files = sorted(SRC_ROOT.rglob("*.py"))
    assert len(files) > 20, f"the scan walked {len(files)} files; the tree layout changed"
    return files


class TestTheGuardIsNotVacuous:
    """A green guard that cannot fail is the defect it is meant to catch (lesson 034)."""

    @pytest.mark.parametrize(
        ("source", "why"),
        [
            ('c = conn.execute("SELECT a FROM t WHERE updated_at > ?", (x,))', "compared"),
            ('c = conn.execute("SELECT a FROM t ORDER BY updated_at DESC")', "clause"),
            ('c = conn.execute("SELECT id, updated_at FROM t")', "clause"),
            ('c = conn.execute("UPDATE t SET a = 1 AND updated_at = 2")', "clause"),
            ('sql = "JOIN x ON b.updated_at = c.d"', "clause"),
            ("stale = row['updated_at'] > cutoff", "loaded"),
            ("def f():\n    return updated_at", "loaded"),
        ],
        ids=["where-gt", "order-by", "projection", "predicate-and", "join-on", "subscript", "name"],
    )
    def test_it_names_a_read(self, source: str, why: str) -> None:
        findings = scan_source(source)
        assert findings, f"the guard let a read through: {source}"
        assert any(why in str(f) for f in findings), [str(f) for f in findings]

    @pytest.mark.parametrize(
        "source",
        [
            'sql = "UPDATE t SET updated_at = :u"',
            'sql = "INSERT INTO t (a, b, updated_at) VALUES (?, ?, ?)"',
            'sql = "UPDATE t SET updated_at = :u WHERE id = :i"',
            'row = {"updated_at": utc_now()}',
            'row["updated_at"] = utc_now()',
            'op.create_table("t", sa.Column("updated_at", sa.Text(), nullable=False))',
            'def f(conn):\n    """The re-pull moves only updated_at, which is bookkeeping."""\n    return 0\n',
            'c = 1  # updated_at is never a change signal\nsql = "SELECT 1"\n',
        ],
        ids=[
            "set",
            "insert-list",
            "set-then-where",
            "dict-key",
            "store",
            "declaration",
            "docstring",
            "comment",
        ],
    )
    def test_it_lets_a_write_through(self, source: str) -> None:
        assert scan_source(source) == [], [str(f) for f in scan_source(source)]

    def test_a_load_outside_a_string_is_a_read_even_when_named_a_variable(self) -> None:
        tree = ast.parse("def f(row):\n    return row['updated_at']\n")
        assert _python_loads(tree) == [2]
        assert _python_loads(ast.parse("row['updated_at'] = 'x'\n")) == []

    def test_prose_is_exempt_only_because_it_cannot_execute(self) -> None:
        """If the exemption were the *line* rather than the docstring, a read would hide under it."""
        text = 'def f(conn):\n    """updated_at is never read."""\n    return conn.execute("SELECT updated_at FROM t")\n'
        findings = scan_source(text)
        assert len(findings) == 1, [str(f) for f in findings]
        assert findings[0].lineno == 3, "the read is on the return line, not the docstring"


class TestProductionTreeIsClean:
    def test_every_occurrence_in_src_is_a_write(self) -> None:
        findings: list[Finding] = []
        occurrences = 0
        for path in _sources():
            text = path.read_text(encoding="utf-8")
            occurrences += len(re.findall(rf"\b{NAME}\b", text))
            findings.extend(scan_source(text, path))
        assert occurrences > 0, (
            "the name vanished from src/; delete this guard, do not let it pass empty"
        )
        assert findings == [], "\n".join(str(f) for f in findings)

    def test_the_guarded_upsert_decides_on_the_key_not_on_the_column(self) -> None:
        """AC8's shape, stated as a clause rather than a grep.

        `repository.py`'s guarded upsert must compare the **key** and maintain `updated_at`; the moment
        the guard clause reads the column, an identical re-pull stops being a no-op — every row looks new
        and the incremental path becomes a full scan that believes it is incremental.
        """
        text = (SRC_ROOT / "garsync" / "db" / "repository.py").read_text(encoding="utf-8")
        clauses = re.findall(r"(?is)DO UPDATE SET(.*?)\n\s*WHERE", text)
        assert clauses, "the guarded upsert moved; this assertion has to move with it"
        for clause in clauses:
            assert NAME in clause, "a DO UPDATE that does not maintain the column"
            assert not re.search(rf"{NAME}\s*(>=|<=|<>|!=|>|<)", clause), "the guard compares it"
