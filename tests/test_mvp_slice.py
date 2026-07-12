"""Tests for source mapping validation, schema backwards compatibility, and digest ordering."""

import copy
import json
from datetime import datetime
from pathlib import Path

import pytest

from hardcore_bot.models import PriceObservation, Product
from hardcore_bot.storage import (
    connect,
    init_db,
    add_observations,
    latest_observations,
    _row_to_obs,
)
from hardcore_bot.source_mappings import (
    ALLOWED_SOURCES,
    check_mappings,
    validate_mappings,
    MappingValidationError,
    load_mappings,
)
from hardcore_bot.digest import (
    group_latest_by_product,
    build_digest_entries,
    PriceEntry,
    DigestEntry,
)


# ---------------------------------------------------------------------------
# Schema backwards compatibility
# ---------------------------------------------------------------------------

def test_new_db_has_provenance_columns(tmp_path):
    """A freshly created DB has the new source provenance columns."""
    db = tmp_path / "fresh.sqlite3"
    con = connect(db)
    init_db(con)
    cols = {row[1] for row in con.execute("PRAGMA table_info(price_observations)")}
    for col in ("source", "source_product_id", "store_or_filial", "old_price_uah", "discount_until", "raw_json"):
        assert col in cols, f"Missing column: {col}"


def test_old_schema_is_migrated(tmp_path):
    """A DB created without provenance columns gets them via migration."""
    db = tmp_path / "old.sqlite3"
    con = connect(db)
    # Create the *old* schema manually (without new columns)
    con.executescript("""
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
          url TEXT
        );
    """)
    con.commit()
    # Verify old schema has no new columns
    cols_before = {row[1] for row in con.execute("PRAGMA table_info(price_observations)")}
    for col in ("source", "old_price_uah", "raw_json"):
        assert col not in cols_before, f"Column should not exist yet: {col}"
    # Run migration via init_db
    init_db(con)
    cols_after = {row[1] for row in con.execute("PRAGMA table_info(price_observations)")}
    for col in ("source", "source_product_id", "store_or_filial", "old_price_uah", "discount_until", "raw_json"):
        assert col in cols_after, f"Column missing after migration: {col}"


def test_old_observations_still_readable_after_migration(tmp_path):
    """Observations inserted before migration remain readable after init_db()."""
    db = tmp_path / "migrate_read.sqlite3"
    con = connect(db)
    # Old schema
    con.executescript("""
        CREATE TABLE products (
          id TEXT PRIMARY KEY,
          title_uk TEXT NOT NULL,
          title_ru TEXT NOT NULL,
          category TEXT NOT NULL,
          size TEXT NOT NULL
        );
        CREATE TABLE price_observations (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          product_id TEXT NOT NULL REFERENCES products(id),
          retailer TEXT NOT NULL,
          price_uah REAL NOT NULL,
          observed_at TEXT NOT NULL,
          available INTEGER NOT NULL DEFAULT 1,
          url TEXT
        );
        INSERT INTO products(id,title_uk,title_ru,category,size) VALUES('p1','Test','Test','x','1');
        INSERT INTO price_observations(product_id,retailer,price_uah,observed_at,available)
        VALUES('p1','DemoMart',99.0,'2026-07-12T08:00:00',1);
    """)
    con.commit()
    # Migrate
    init_db(con)
    # Read back
    obs_list = latest_observations(con)
    assert len(obs_list) == 1
    assert obs_list[0].product_id == "p1"
    assert obs_list[0].price_uah == 99.0
    assert obs_list[0].retailer == "DemoMart"
    # New fields should be None
    assert obs_list[0].source is None
    assert obs_list[0].old_price_uah is None
    assert obs_list[0].raw_json is None


def test_observation_with_provenance_fields(tmp_path):
    """Can insert and read back observations with full provenance fields."""
    db = tmp_path / "provenance.sqlite3"
    con = connect(db)
    init_db(con)
    con.execute("INSERT INTO products(id,title_uk,title_ru,category,size) VALUES('p1','Test','Test','x','1')")
    con.commit()

    obs = PriceObservation(
        product_id="p1",
        retailer="ATB",
        price_uah=45.50,
        observed_at=datetime(2026, 7, 12, 8, 0),
        available=True,
        url="https://atb.example.com/p1",
        source="atb",
        source_product_id="ATB-123",
        store_or_filial="Київ, вул. Хрещатик, 1",
        old_price_uah=55.0,
        discount_until=datetime(2026, 8, 1, 0, 0),
        raw_json='{"price":45.5,"oldPrice":55.0}',
    )
    add_observations(con, [obs])
    obs_list = latest_observations(con)
    assert len(obs_list) == 1
    loaded = obs_list[0]
    assert loaded.source == "atb"
    assert loaded.source_product_id == "ATB-123"
    assert loaded.store_or_filial == "Київ, вул. Хрещатик, 1"
    assert loaded.old_price_uah == 55.0
    assert loaded.discount_until == datetime(2026, 8, 1, 0, 0)
    assert loaded.raw_json == '{"price":45.5,"oldPrice":55.0}'


# ---------------------------------------------------------------------------
# Source mapping validation
# ---------------------------------------------------------------------------

SEED_PRODUCTS = [
    Product("pepsi-black-2l", "Pepsi Black 2 л", "Pepsi Black 2 л", "beverages", "2 л"),
    Product("aha-muesli-330g", "Muesli 330 г", "Muesli 330 г", "breakfast", "330 г"),
]

SEED_DICT = {p.id: p for p in SEED_PRODUCTS}

VALID_MAPPING = {
    "version": 1,
    "source_priority": ["atb", "fora"],
    "products": [
        {
            "product_id": "pepsi-black-2l",
            "canonical_title": "Pepsi Black 2 l",
            "category": "beverages",
            "size": "2 l",
            "mappings": {
                "atb": {
                    "url": "https://atb.example.com/pepsi",
                    "confidence": "user_seed_exact_url",
                },
                "fora": {
                    "source_product_id": "FORA-42",
                    "confidence": "verified",
                },
            },
        },
        {
            "product_id": "aha-muesli-330g",
            "canonical_title": "AHA Muesli 330g",
            "category": "breakfast",
            "size": "330 g",
            "mappings": {
                "atb": {
                    "url": "https://atb.example.com/muesli",
                    "confidence": "user_seed_exact_url",
                },
            },
        },
    ],
}


def test_valid_mapping_passes():
    errors = validate_mappings(VALID_MAPPING, SEED_DICT)
    assert errors == [], f"Expected no errors, got: {errors}"


def test_valid_mapping_loads(tmp_path):
    f = tmp_path / "valid.json"
    f.write_text(json.dumps(VALID_MAPPING), encoding="utf-8")
    data = load_mappings(f)
    assert data["version"] == 1


def test_unknown_source_fails():
    m = dict(VALID_MAPPING)
    m["products"] = [
        {
            "product_id": "pepsi-black-2l",
            "canonical_title": "Pepsi Black 2 l",
            "category": "beverages",
            "size": "2 l",
            "mappings": {
                "unknown_mart": {
                    "url": "https://unknown.example.com",
                    "confidence": "low",
                },
            },
        },
    ]
    errors = validate_mappings(m, SEED_DICT)
    assert any("unknown_mart" in e for e in errors), f"Expected unknown source error, got: {errors}"


def test_missing_confidence_fails():
    m = copy.deepcopy(VALID_MAPPING)
    m["products"][0]["mappings"]["atb"] = {"url": "https://atb.example.com/pepsi"}
    errors = validate_mappings(m, SEED_DICT)
    assert any("confidence" in e for e in errors), f"Expected missing confidence error: {errors}"


def test_missing_url_and_identifier_fails():
    m = copy.deepcopy(VALID_MAPPING)
    m["products"][0]["mappings"]["atb"] = {"confidence": "low"}
    errors = validate_mappings(m, SEED_DICT)
    assert any("url" in e.lower() or "source_product_id" in e or "query" in e for e in errors), \
        f"Expected missing identifier error: {errors}"


def test_duplicate_product_id_fails():
    m = copy.deepcopy(VALID_MAPPING)
    m["products"].append(m["products"][0])
    errors = validate_mappings(m, SEED_DICT)
    dup_errors = [e for e in errors if "duplicate" in e]
    assert len(dup_errors) >= 1, f"Expected duplicate error: {errors}"


def test_nonexistent_product_id_fails():
    m = dict(VALID_MAPPING)
    m["products"] = [
        {
            "product_id": "nonexistent-sku",
            "canonical_title": "Ghost",
            "category": "x",
            "size": "1",
            "mappings": {
                "atb": {
                    "url": "https://atb.example.com/ghost",
                    "confidence": "low",
                },
            },
        },
    ]
    errors = validate_mappings(m, SEED_DICT)
    assert any("nonexistent-sku" in e for e in errors), f"Expected nonexistent product error: {errors}"


def test_missing_products_key_is_validated():
    errors = validate_mappings({"version": 1})
    assert any("products" in e for e in errors), f"Expected products key error: {errors}"


def test_source_priority_unknown_source():
    m = dict(VALID_MAPPING)
    m["source_priority"] = ["atb", "fakestore"]
    errors = validate_mappings(m, SEED_DICT)
    assert any("fakestore" in e for e in errors), f"Expected unknown source_priority error: {errors}"


def test_allowed_sources_frozenset():
    assert "atb" in ALLOWED_SOURCES
    assert "fora" in ALLOWED_SOURCES
    assert "thrash" in ALLOWED_SOURCES
    assert "auchan" in ALLOWED_SOURCES
    assert "novus" in ALLOWED_SOURCES
    assert len(ALLOWED_SOURCES) == 5


# ---------------------------------------------------------------------------
# check_mappings convenience (file-based)
# ---------------------------------------------------------------------------

def test_check_mappings_valid(tmp_path):
    seed = tmp_path / "seed.json"
    seed.write_text(json.dumps([
        {"id": "pepsi-black-2l", "title_uk": "X", "title_ru": "X", "category": "x", "size": "1"},
    ]), encoding="utf-8")
    mapping = tmp_path / "map.json"
    mapping.write_text(json.dumps({
        "version": 1,
        "products": [
            {
                "product_id": "pepsi-black-2l",
                "canonical_title": "Pepsi",
                "category": "x",
                "size": "1",
                "mappings": {
                    "atb": {
                        "url": "https://atb.example.com/p",
                        "confidence": "ok",
                    },
                },
            },
        ],
    }), encoding="utf-8")
    errors = check_mappings(mapping, seed)
    assert errors == [], f"Expected no errors, got: {errors}"


def test_check_mappings_missing_seed_file(tmp_path):
    mapping = tmp_path / "map.json"
    mapping.write_text(json.dumps(VALID_MAPPING), encoding="utf-8")
    errors = check_mappings(mapping, tmp_path / "no_such_file.json")
    assert len(errors) == 1
    assert "Could not load seed" in errors[0]


# ---------------------------------------------------------------------------
# Digest foundation — grouping and ordering
# ---------------------------------------------------------------------------

NOW = datetime(2026, 7, 12, 9, 0, 0)


def test_group_latest_by_product_sorts_best_first():
    """group_latest_by_product returns available items sorted by price ASC."""
    obs = [
        PriceObservation("p1", "Auchan", 50.0, NOW, True),
        PriceObservation("p1", "ATB", 45.0, NOW, True),
        PriceObservation("p1", "Fora", 48.0, NOW, False),
    ]
    groups = group_latest_by_product(obs)
    assert "p1" in groups
    entries = groups["p1"]
    # Available first, then unavailable; available sorted by price
    assert len(entries) == 3
    assert entries[0].retailer == "ATB"  # cheapest available
    assert entries[0].available is True
    assert entries[1].retailer == "Auchan"  # second cheapest available
    assert entries[2].retailer == "Fora"  # unavailable last


def test_group_latest_by_product_multiple_products():
    obs = [
        PriceObservation("p1", "ATB", 45.0, NOW, True),
        PriceObservation("p2", "Fora", 30.0, NOW, True),
    ]
    groups = group_latest_by_product(obs)
    assert set(groups.keys()) == {"p1", "p2"}


def test_build_digest_entries_best_first():
    """build_digest_entries marks the cheapest available as best."""
    products = [Product("p1", "Test UK", "Test RU", "x", "1")]
    obs = [
        PriceObservation("p1", "Auchan", 50.0, NOW, True),
        PriceObservation("p1", "ATB", 45.0, NOW, True),
    ]
    digest = build_digest_entries(products, obs)
    assert len(digest) == 1
    entry = digest[0]
    assert len(entry.price_entries) == 2
    # ATB is cheapest (45 < 50)
    assert entry.price_entries[0].retailer == "ATB"
    assert entry.price_entries[0].is_best is True
    assert entry.price_entries[1].retailer == "Auchan"
    assert entry.price_entries[1].is_best is False


def test_build_digest_entries_missing_covered_source():
    """When covered_sources includes a source with no observation, it appears as unavailable."""
    products = [Product("p1", "Test UK", "Test RU", "x", "1")]
    obs = [
        PriceObservation("p1", "ATB", 45.0, NOW, True, source="atb"),
    ]
    digest = build_digest_entries(products, obs, covered_sources=["atb", "fora"])
    assert len(digest) == 1
    retailers = [pe.retailer for pe in digest[0].price_entries]
    assert "ATB" in retailers
    assert "fora" in retailers  # missing source added
    # Find the fora entry
    fora_entry = next(pe for pe in digest[0].price_entries if pe.retailer == "fora")
    assert fora_entry.available is False
    assert fora_entry.price_uah is None


def test_build_digest_entries_watched_ids_filter():
    """Only watched product IDs appear if watched_ids is provided."""
    products = [
        Product("p1", "Test UK", "Test RU", "x", "1"),
        Product("p2", "Test2 UK", "Test2 RU", "x", "2"),
    ]
    obs = [
        PriceObservation("p1", "ATB", 45.0, NOW, True),
        PriceObservation("p2", "Fora", 30.0, NOW, True),
    ]
    digest = build_digest_entries(products, obs, watched_ids={"p1"})
    assert len(digest) == 1
    assert digest[0].product.id == "p1"


def test_build_digest_entries_watched_product_without_observations():
    """Watched SKUs remain visible before the first source observation."""
    products = [Product("p1", "Test UK", "Test RU", "x", "1")]
    digest = build_digest_entries(
        products,
        [],
        covered_sources=["atb", "fora"],
        watched_ids={"p1"},
    )

    assert len(digest) == 1
    assert digest[0].product.id == "p1"
    assert [entry.retailer for entry in digest[0].price_entries] == ["atb", "fora"]
    assert all(entry.available is False for entry in digest[0].price_entries)
    assert all(entry.price_uah is None for entry in digest[0].price_entries)


def test_build_digest_entries_all_products_when_no_watch():
    """Without watched_ids, all products with observations appear."""
    products = [
        Product("p1", "Test UK", "Test RU", "x", "1"),
        Product("p2", "Test2 UK", "Test2 RU", "x", "2"),
    ]
    obs = [
        PriceObservation("p1", "ATB", 45.0, NOW, True),
        PriceObservation("p2", "Fora", 30.0, NOW, True),
    ]
    digest = build_digest_entries(products, obs)
    assert len(digest) == 2


def test_build_digest_entries_unavailable_items_marked():
    """Unavailable observations appear with available=False and don't get is_best."""
    products = [Product("p1", "Test UK", "Test RU", "x", "1")]
    obs = [
        PriceObservation("p1", "ATB", 45.0, NOW, False),  # out of stock
        PriceObservation("p1", "Fora", 50.0, NOW, True),
    ]
    digest = build_digest_entries(products, obs)
    assert len(digest[0].price_entries) == 2
    # Fora (available) should be first, best
    assert digest[0].price_entries[0].retailer == "Fora"
    assert digest[0].price_entries[0].is_best is True
    assert digest[0].price_entries[1].retailer == "ATB"
    assert digest[0].price_entries[1].available is False
    assert digest[0].price_entries[1].is_best is False


def test_price_entry_dataclass():
    pe = PriceEntry("ATB", 45.0, True, "atb", "https://atb.example.com", is_best=True)
    assert pe.retailer == "ATB"
    assert pe.price_uah == 45.0
    assert pe.available is True
    assert pe.is_best is True


def test_digest_entry_dataclass():
    p = Product("p1", "T", "T", "x", "1")
    pe = PriceEntry("ATB", 45.0, True, "atb", None)
    de = DigestEntry(product=p, price_entries=[pe])
    assert de.product.id == "p1"
    assert len(de.price_entries) == 1


# ---------------------------------------------------------------------------
# Backward compatibility: old-style PriceObservation construction still works
# ---------------------------------------------------------------------------

def test_price_observation_backward_compatible():
    """Creating a PriceObservation with only original fields still works."""
    obs = PriceObservation("p1", "Demo", 99.0, NOW, True)
    assert obs.source is None
    assert obs.old_price_uah is None
    assert obs.raw_json is None


def test_price_observation_old_style_in_storage(tmp_path):
    """Old 6-arg PriceObservation can be stored and read back."""
    db = tmp_path / "old_style.sqlite3"
    con = connect(db)
    init_db(con)
    con.execute("INSERT INTO products(id,title_uk,title_ru,category,size) VALUES('p1','T','T','x','1')")
    con.commit()
    old = PriceObservation("p1", "Demo", 99.0, NOW, True, "https://demo.example.com")
    add_observations(con, [old])
    loaded = latest_observations(con)
    assert len(loaded) == 1
    assert loaded[0].product_id == "p1"
    assert loaded[0].price_uah == 99.0
    assert loaded[0].source is None
