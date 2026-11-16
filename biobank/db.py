"""Thin Python access layer: open the database and run the named queries safely."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUERY_DIR = ROOT / "queries"
DEFAULT_DB = ROOT / "build" / "biobank.db"


@contextmanager
def connect(path: str | Path = DEFAULT_DB, readonly: bool = True) -> Iterator[sqlite3.Connection]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"{path} not found; build it with `python -m biobank build`")
    uri = f"file:{path}?mode=ro" if readonly else f"file:{path}"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
    finally:
        con.close()


def list_queries() -> dict[str, str]:
    """Map query name (file stem) to the question in its header comment."""
    out = {}
    for f in sorted(QUERY_DIR.glob("*.sql")):
        header = " ".join(
            line.removeprefix("--").strip() for line in f.read_text().splitlines() if line.startswith("--")
        )
        out[f.stem] = header.split("Concepts:")[0].removeprefix("Question:").strip()
    return out


def run_named(con: sqlite3.Connection, name: str) -> tuple[list[str], list[tuple]]:
    """Run one of the files in ``queries/`` by its name or number prefix ("03")."""
    matches = [f for f in sorted(QUERY_DIR.glob("*.sql")) if f.stem == name or f.stem.startswith(f"{name}_")]
    if len(matches) != 1:
        raise KeyError(f"No unique query named {name!r}; choose from {list(list_queries())}")
    cur = con.execute(matches[0].read_text())
    return [d[0] for d in cur.description], [tuple(r) for r in cur.fetchall()]


def individuals_with_insertion_in_gene(con: sqlite3.Connection, symbol: str) -> list[sqlite3.Row]:
    """Example of a parameterised query: user input is passed as a parameter, never pasted into SQL."""
    sql = """
        SELECT DISTINCT i.external_code, i.population, c.genotype, f.name AS family
        FROM genes g
        JOIN te_insertions t   ON t.chrom_id = g.chrom_id AND t.start_bp < g.end_bp AND g.start_bp < t.end_bp
        JOIN te_families f     ON f.family_id = t.family_id
        JOIN insertion_calls c ON c.insertion_id = t.insertion_id
        JOIN v_good_runs r     ON r.run_id = c.run_id
        JOIN individuals i     ON i.individual_id = r.individual_id
        WHERE g.symbol = ?
        ORDER BY i.external_code
    """
    return con.execute(sql, (symbol,)).fetchall()


def explain(con: sqlite3.Connection, sql: str) -> list[str]:
    """SQLite's query plan, to check that an index is used."""
    return [row[-1] for row in con.execute(f"EXPLAIN QUERY PLAN {sql}")]


def format_table(columns: list[str], rows: list[tuple], limit: int = 25) -> str:
    shown = [tuple("" if v is None else str(v) for v in r) for r in rows[:limit]]
    widths = [max([len(c)] + [len(r[i]) for r in shown]) for i, c in enumerate(columns)]
    line = "  ".join(c.ljust(w) for c, w in zip(columns, widths))
    sep = "  ".join("-" * w for w in widths)
    body = ["  ".join(v.ljust(w) for v, w in zip(r, widths)) for r in shown]
    more = [f"... {len(rows) - limit} more rows"] if len(rows) > limit else []
    return "\n".join([line, sep, *body, *more])
