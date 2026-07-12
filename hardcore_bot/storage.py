from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .models import PriceObservation, Product, WatchRule

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS users (
  user_id INTEGER PRIMARY KEY,
  lang TEXT NOT NULL DEFAULT 'uk',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
  id TEXT PRIMARY KEY,
  title_uk TEXT NOT NULL,
  title_ru TEXT NOT NULL,
  category TEXT NOT NULL,
  size TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS price_observations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  product_id TEXT NOT NULL REFERENCES products(id),
  retailer TEXT NOT NULL,
  price_uah REAL NOT NULL,
  observed_at TEXT NOT NULL,
  available INTEGER NOT NULL DEFAULT 1,
  url TEXT,
  source TEXT,
  source_product_id TEXT,
  store_or_filial TEXT,
  old_price_uah REAL,
  discount_until TEXT,
  raw_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_price_product_time ON price_observations(product_id, observed_at DESC);
CREATE TABLE IF NOT EXISTS watchlists (
  user_id INTEGER NOT NULL,
  product_id TEXT NOT NULL REFERENCES products(id),
  drop_percent REAL NOT NULL DEFAULT 15,
  threshold_uah REAL,
  best_today INTEGER NOT NULL DEFAULT 1,
  cooldown_hours INTEGER NOT NULL DEFAULT 24,
  PRIMARY KEY(user_id, product_id)
);
CREATE TABLE IF NOT EXISTS alerts_sent (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  product_id TEXT NOT NULL,
  retailer TEXT NOT NULL,
  reason TEXT NOT NULL,
  price_uah REAL NOT NULL,
  sent_at TEXT NOT NULL
);
"""


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def connect(path: str | Path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


def init_db(con: sqlite3.Connection) -> None:
    con.executescript(SCHEMA)
    _migrate_price_observations(con)
    con.commit()


# Columns added in the MVP slice (2026-07-12) for source provenance.
_NEW_OBS_COLUMNS = {
    "source": "TEXT",
    "source_product_id": "TEXT",
    "store_or_filial": "TEXT",
    "old_price_uah": "REAL",
    "discount_until": "TEXT",
    "raw_json": "TEXT",
}


def _migrate_price_observations(con: sqlite3.Connection) -> None:
    """Add new columns if missing (backward-compatible schema migration)."""
    existing = {row[1] for row in con.execute("PRAGMA table_info(price_observations)")}
    for col, coltype in _NEW_OBS_COLUMNS.items():
        if col not in existing:
            con.execute(f"ALTER TABLE price_observations ADD COLUMN {col} {coltype}")


def load_seed_products(path: str | Path) -> list[Product]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Product(**item) for item in data]


def upsert_products(con: sqlite3.Connection, products: Iterable[Product]) -> None:
    con.executemany(
        "INSERT INTO products(id,title_uk,title_ru,category,size) VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title_uk=excluded.title_uk,title_ru=excluded.title_ru,category=excluded.category,size=excluded.size",
        [(p.id, p.title_uk, p.title_ru, p.category, p.size) for p in products],
    )
    con.commit()


def list_products(con: sqlite3.Connection) -> list[Product]:
    return [Product(**dict(row)) for row in con.execute("SELECT * FROM products ORDER BY category,id")]


def add_observations(con: sqlite3.Connection, observations: Iterable[PriceObservation]) -> int:
    rows = [
        (
            o.product_id, o.retailer, o.price_uah, o.observed_at.isoformat(),
            int(o.available), o.url,
            o.source, o.source_product_id, o.store_or_filial,
            o.old_price_uah,
            o.discount_until.isoformat() if o.discount_until else None,
            o.raw_json,
        )
        for o in observations
    ]
    con.executemany(
        "INSERT INTO price_observations(product_id,retailer,price_uah,observed_at,available,url,"
        "source,source_product_id,store_or_filial,old_price_uah,discount_until,raw_json) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    con.commit()
    return len(rows)


def latest_observations(con: sqlite3.Connection) -> list[PriceObservation]:
    rows = con.execute("""
      SELECT po.* FROM price_observations po
      JOIN (
        SELECT product_id, retailer, MAX(observed_at) AS max_time
        FROM price_observations GROUP BY product_id, retailer
      ) latest ON latest.product_id=po.product_id AND latest.retailer=po.retailer AND latest.max_time=po.observed_at
      ORDER BY po.product_id, po.price_uah ASC
    """).fetchall()
    return [_row_to_obs(r) for r in rows]


def all_observations(con: sqlite3.Connection) -> list[PriceObservation]:
    return [_row_to_obs(r) for r in con.execute("SELECT * FROM price_observations ORDER BY observed_at DESC")]


def previous_price_before_latest(con: sqlite3.Connection, product_id: str, retailer: str) -> float | None:
    rows = con.execute(
        "SELECT price_uah FROM price_observations WHERE product_id=? AND retailer=? ORDER BY observed_at DESC LIMIT 2",
        (product_id, retailer),
    ).fetchall()
    return float(rows[1]["price_uah"]) if len(rows) > 1 else None


def ensure_user(con: sqlite3.Connection, user_id: int, lang: str = "uk") -> None:
    con.execute("INSERT INTO users(user_id, lang, created_at) VALUES(?,?,?) ON CONFLICT(user_id) DO NOTHING", (user_id, lang, utcnow().isoformat()))
    con.commit()


def set_user_lang(con: sqlite3.Connection, user_id: int, lang: str) -> None:
    ensure_user(con, user_id, lang)
    con.execute("UPDATE users SET lang=? WHERE user_id=?", (lang, user_id))
    con.commit()


def add_watch(con: sqlite3.Connection, rule: WatchRule) -> None:
    ensure_user(con, rule.user_id)
    con.execute(
        "INSERT INTO watchlists(user_id,product_id,drop_percent,threshold_uah,best_today,cooldown_hours) VALUES(?,?,?,?,?,?) ON CONFLICT(user_id,product_id) DO UPDATE SET drop_percent=excluded.drop_percent,threshold_uah=excluded.threshold_uah,best_today=excluded.best_today,cooldown_hours=excluded.cooldown_hours",
        (rule.user_id, rule.product_id, rule.drop_percent, rule.threshold_uah, int(rule.best_today), rule.cooldown_hours),
    )
    con.commit()


def count_observations(con: sqlite3.Connection) -> int:
    return int(con.execute("SELECT COUNT(*) AS c FROM price_observations").fetchone()["c"])


def _row_to_obs(row: sqlite3.Row) -> PriceObservation:
    keys = row.keys()
    return PriceObservation(
        product_id=row["product_id"],
        retailer=row["retailer"],
        price_uah=float(row["price_uah"]),
        observed_at=datetime.fromisoformat(row["observed_at"]),
        available=bool(row["available"]),
        url=row["url"] if "url" in keys else None,
        source=row["source"] if "source" in keys else None,
        source_product_id=row["source_product_id"] if "source_product_id" in keys else None,
        store_or_filial=row["store_or_filial"] if "store_or_filial" in keys else None,
        old_price_uah=(
            float(row["old_price_uah"])
            if "old_price_uah" in keys and row["old_price_uah"] is not None
            else None
        ),
        discount_until=(
            datetime.fromisoformat(row["discount_until"])
            if "discount_until" in keys and row["discount_until"]
            else None
        ),
        raw_json=row["raw_json"] if "raw_json" in keys else None,
    )
