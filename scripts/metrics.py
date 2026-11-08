#!/usr/bin/env python3
"""Sprint-report metrics for InspectIQ.

Static analysis of the source tree and git history. Does NOT connect
to the database — safe to run on any checkout.

Excluded everywhere: ``migrations/``, ``__init__.py``, ``manage.py``.
The root ``conftest.py`` is counted under ``config`` as test
infrastructure.

Usage:
    python scripts/metrics.py                   # all-time
    python scripts/metrics.py --since 2026-10-15   # Sprint-2 only
"""

from __future__ import annotations

import argparse
import ast
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APPS = ("accounts", "stores", "inspections", "tickets", "common")

# Collapse duplicate git identities. Add aliases here as new teammate
# machines appear in the log with different committer names.
IDENTITY = {
    "rohan": "rohan",
    "Rohan Hashmi": "rohan",
    "rohanhashmi": "rohan",
    "rohanhashmi2": "rohan",
    "McIntosh": "McIntosh",
    "Jacob McIntosh": "McIntosh",
    "DemingLei": "DemingLei",
    "Deming Lei": "DemingLei",
}


def canonical(name: str) -> str:
    return IDENTITY.get(name, name)


# ---------- file selection ----------


def _skip(path: Path) -> bool:
    return (
        "migrations" in path.parts
        or path.name == "__init__.py"
        or path.name == "manage.py"
    )


def prod_files(app: str) -> list[Path]:
    root = ROOT / "apps" / app
    return sorted(
        p for p in root.rglob("*.py") if "tests" not in p.parts and not _skip(p)
    )


def test_files(app: str) -> list[Path]:
    root = ROOT / "apps" / app / "tests"
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*.py") if not _skip(p))


def config_prod() -> list[Path]:
    return sorted(p for p in (ROOT / "config").rglob("*.py") if not _skip(p))


def config_test() -> list[Path]:
    conftest = ROOT / "conftest.py"
    return [conftest] if conftest.exists() else []


# ---------- line / ast counts ----------


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def nonblank(path: Path) -> int:
    return sum(1 for line in _read(path).splitlines() if line.strip())


def total_lines(path: Path) -> int:
    return len(_read(path).splitlines())


def ast_counts(path: Path) -> tuple[int, int]:
    """Return (classes, functions/methods) counted by AST walk.

    Counts nested classes and nested functions as well as top-level
    ones — "methods" in the task spec means functions inside classes.
    """
    try:
        tree = ast.parse(_read(path))
    except SyntaxError:
        return (0, 0)
    classes = sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
    funcs = sum(
        1
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    return classes, funcs


# ---------- git ----------


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def author_lines(since: str | None = None) -> dict[str, tuple[int, int]]:
    """Return {canonical_name: (added, deleted)} from ``git log --numstat``.

    Merges are excluded. Binary file rows (``-\t-\t<file>``) are skipped.
    """
    cmd = ["log", "--no-merges", "--pretty=tformat:AUTHOR:%an", "--numstat"]
    if since:
        cmd.append(f"--since={since}")
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    current: str | None = None
    for line in git(*cmd).splitlines():
        if line.startswith("AUTHOR:"):
            current = canonical(line[len("AUTHOR:") :])
            continue
        if not line.strip() or current is None:
            continue
        parts = line.split("\t")
        if len(parts) < 3 or parts[0] == "-":
            continue
        totals[current][0] += int(parts[0])
        totals[current][1] += int(parts[1])
    return {k: (a, d) for k, (a, d) in totals.items()}


def lines_added_per_file_author(
    since: str | None = None,
) -> dict[str, dict[str, int]]:
    """Return ``{path: {canonical_name: added_lines}}`` from numstat.

    Sums ``git log --no-merges --numstat`` per (file, author). Binary
    rows (numstat ``-``) are skipped, and paths no longer tracked
    (deleted, renamed) are filtered out. ``__pycache__/`` and ``.pyc``
    paths are excluded — attribution on a build cache is meaningless.
    """

    def keep(p: str) -> bool:
        return "__pycache__/" not in p and not p.endswith(".pyc")

    tracked = {p for p in git("ls-files").splitlines() if keep(p)}
    cmd = ["log", "--no-merges", "--pretty=tformat:AUTHOR:%an", "--numstat"]
    if since:
        cmd.append(f"--since={since}")
    data: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    author: str | None = None
    for line in git(*cmd).splitlines():
        if line.startswith("AUTHOR:"):
            author = canonical(line[len("AUTHOR:") :])
            continue
        if not line.strip() or author is None:
            continue
        parts = line.split("\t")
        if len(parts) < 3 or parts[0] == "-":
            continue
        path = parts[2]
        if path not in tracked:
            continue
        data[path][author] += int(parts[0])
    return data


def area_for(path: str) -> str:
    """Classify a tracked path into the Section-7 rollup bucket.

    ``apps/<app>/...``       → that app
    ``templates/<app>/...``  → that app (templates count with their feature)
    ``config/...``           → config
    anything else            → other (README, docs, pyproject, etc.)
    """
    parts = Path(path).parts
    if not parts:
        return "other"
    if parts[0] == "apps" and len(parts) > 1:
        return parts[1]
    if parts[0] == "templates" and len(parts) > 1:
        return parts[1]
    if parts[0] == "config":
        return "config"
    return "other"


# ---------- render ----------


def table(headers: list[str], rows: list[list]) -> str:
    cols = len(headers)
    widths = [len(h) for h in headers]
    for r in rows:
        for i in range(cols):
            widths[i] = max(widths[i], len(str(r[i])))
    lines = ["  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))]
    lines.append("  ".join("-" * w for w in widths))
    lines.extend(
        "  ".join(str(r[i]).ljust(widths[i]) for i in range(cols)) for r in rows
    )
    return "\n".join(lines)


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


# ---------- sections ----------


def section1() -> list[list]:
    """Per-app / config totals."""
    totals = [0, 0, 0, 0]
    rows: list[list] = []
    areas = [(app, prod_files(app), test_files(app)) for app in APPS]
    areas.append(("config", config_prod(), config_test()))
    for area, prod, tests in areas:
        cls = fn = 0
        for p in prod:
            c, f = ast_counts(p)
            cls += c
            fn += f
        p_loc = sum(nonblank(p) for p in prod)
        t_loc = sum(nonblank(p) for p in tests)
        rows.append([area, cls, fn, p_loc, t_loc])
        for i, v in enumerate([cls, fn, p_loc, t_loc]):
            totals[i] += v
    rows.append(["-- total --", *totals])
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--since", help="git --since filter (e.g. 2026-10-15) for Section 5"
    )
    args = ap.parse_args()

    bar = "=" * 72
    print(bar)
    print("InspectIQ metrics")
    print(bar)
    print("Non-blank LOC throughout Sections 1, 2 and 3. Sections 4–7 use")
    print("git numstat added-line totals (merges excluded).")
    print("Excluded from Sections 1, 3 and 7: migrations/, __init__.py, manage.py.")
    print("Root conftest.py counts under 'config' as test infrastructure.")
    print()

    print("1. Per app / config — classes, funcs/methods, prod LOC, test LOC\n")
    print(
        table(
            ["area", "classes", "funcs", "prod LOC", "test LOC"],
            section1(),
        )
    )
    print()

    print("2. Templates and stylesheets (non-blank LOC)\n")
    tfiles = sorted((ROOT / "templates").rglob("*.html"))
    cfiles = sorted((ROOT / "apps").rglob("*.css"))
    print(
        table(
            ["kind", "files", "LOC"],
            [
                ["templates (.html)", len(tfiles), sum(nonblank(p) for p in tfiles)],
                ["stylesheets (.css)", len(cfiles), sum(nonblank(p) for p in cfiles)],
            ],
        )
    )
    print()

    print("3. Per-file non-blank LOC\n")
    print("   -- production --")
    rows_p: list[list] = []
    for app in APPS:
        rows_p.extend([rel(p), nonblank(p)] for p in prod_files(app))
    rows_p.extend([rel(p), nonblank(p)] for p in config_prod())
    print(table(["file", "LOC"], rows_p))
    print()
    print("   -- tests --")
    rows_t: list[list] = []
    for app in APPS:
        rows_t.extend([rel(p), nonblank(p)] for p in test_files(app))
    rows_t.extend([rel(p), nonblank(p)] for p in config_test())
    print(table(["file", "LOC"], rows_t))
    print()

    print("4. Per-author line totals (git log --no-merges, all time)\n")
    stats = author_lines()
    rows = sorted(
        ([name, a, d, a - d] for name, (a, d) in stats.items()),
        key=lambda r: -r[1],
    )
    print(table(["author", "added", "deleted", "net"], rows))
    print()

    if args.since:
        print(f"5. Per-author line totals since {args.since}\n")
        stats_since = author_lines(since=args.since)
        if not stats_since:
            print(f"(no commits since {args.since})")
        else:
            rows_s = sorted(
                ([name, a, d, a - d] for name, (a, d) in stats_since.items()),
                key=lambda r: -r[1],
            )
            print(table(["author", "added", "deleted", "net"], rows_s))
    else:
        print("5. Per-author line totals since <date>\n")
        print("(skipped — pass --since YYYY-MM-DD to enable)")
    print()

    print("6. Lines added per author per file (git log --no-merges --numstat)\n")
    print("   Rows with 0 added lines are omitted.\n")
    by_file = lines_added_per_file_author()
    rows_6: list[list] = []
    for path in sorted(by_file.keys()):
        for author, added in sorted(
            by_file[path].items(), key=lambda kv: (-kv[1], kv[0])
        ):
            if added == 0:
                continue
            rows_6.append([path, author, added])
    print(table(["path", "author", "added"], rows_6))
    print()

    print("7. Per-app × per-author rollup of Section 6 (lines added, %)\n")
    rollup: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for path, by_author in by_file.items():
        bucket = area_for(path)
        for author, added in by_author.items():
            rollup[bucket][author] += added
    # Order authors by project-wide contribution desc, matching Section 4.
    repo_totals: dict[str, int] = defaultdict(int)
    for by in rollup.values():
        for a, added in by.items():
            repo_totals[a] += added
    authors = sorted(repo_totals, key=lambda a: (-repo_totals[a], a))
    area_order = [a for a in (*APPS, "config", "other") if a in rollup]
    rows_7: list[list] = []
    repo_by_author: dict[str, int] = defaultdict(int)
    repo_total = 0
    for area in area_order:
        area_total = sum(rollup[area].values())
        row = [area]
        for a in authors:
            added = rollup[area].get(a, 0)
            pct = (added / area_total * 100) if area_total else 0.0
            row.append(f"{added} ({pct:.1f}%)")
            repo_by_author[a] += added
        row.append(str(area_total))
        rows_7.append(row)
        repo_total += area_total
    total_row: list = ["-- total --"]
    for a in authors:
        added = repo_by_author[a]
        pct = (added / repo_total * 100) if repo_total else 0.0
        total_row.append(f"{added} ({pct:.1f}%)")
    total_row.append(str(repo_total))
    rows_7.append(total_row)
    print(table(["area", *authors, "total"], rows_7))


if __name__ == "__main__":
    main()
