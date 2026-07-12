from __future__ import annotations

import argparse
from pathlib import Path

from .collectors import DemoCollector
from .formatting import format_digest
from .storage import connect, init_db, load_seed_products, upsert_products, list_products, add_observations, latest_observations, count_observations

DEFAULT_SEED = Path(__file__).resolve().parent.parent / "data" / "seed_products.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hardcore-bot")
    parser.add_argument("--db", default="data/hardcore.sqlite3")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-db")
    seed = sub.add_parser("seed")
    seed.add_argument("--seed-file", default=str(DEFAULT_SEED))
    sub.add_parser("collect-demo")
    digest = sub.add_parser("digest")
    digest.add_argument("--lang", choices=["uk", "ru"], default="uk")
    args = parser.parse_args(argv)

    con = connect(args.db)
    if args.cmd == "init-db":
        init_db(con)
        print(f"initialized {args.db}")
    elif args.cmd == "seed":
        init_db(con)
        products = load_seed_products(args.seed_file)
        upsert_products(con, products)
        print(f"seeded {len(products)} products")
    elif args.cmd == "collect-demo":
        init_db(con)
        products = list_products(con)
        if not products:
            products = load_seed_products(DEFAULT_SEED)
            upsert_products(con, products)
        observations = DemoCollector().collect(products)
        print(f"inserted {add_observations(con, observations)} observations")
    elif args.cmd == "digest":
        products = list_products(con)
        print(format_digest(products, latest_observations(con), args.lang))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
