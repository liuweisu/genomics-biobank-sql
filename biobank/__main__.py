"""python -m biobank {build | list | run NAME | sql "SELECT ..."}"""

from __future__ import annotations

import argparse

from . import db, generate


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m biobank")
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="create the database with synthetic data")
    b.add_argument("--out", default=str(db.DEFAULT_DB))
    b.add_argument("--seed", type=int, default=42)
    sub.add_parser("list", help="list the analysis queries")
    r = sub.add_parser("run", help="run a query from queries/ by name or number")
    r.add_argument("name")
    s = sub.add_parser("sql", help="run your own read-only SQL")
    s.add_argument("statement")
    args = parser.parse_args()

    if args.cmd == "build":
        path = generate.build(args.out, seed=args.seed)
        print(f"built {path} ({path.stat().st_size / 1e6:.1f} MB)")
    elif args.cmd == "list":
        for name, question in db.list_queries().items():
            print(f"{name:<40} {question}")
    elif args.cmd == "run":
        with db.connect() as con:
            print(db.format_table(*db.run_named(con, args.name)))
    else:
        with db.connect() as con:  # read-only connection: writes fail
            cur = con.execute(args.statement)
            print(db.format_table([d[0] for d in cur.description], [tuple(r) for r in cur.fetchall()]))


if __name__ == "__main__":
    main()
