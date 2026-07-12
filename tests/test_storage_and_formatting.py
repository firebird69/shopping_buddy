from datetime import datetime

from hardcore_bot.collectors import DemoCollector
from hardcore_bot.formatting import format_digest, format_products
from hardcore_bot.storage import connect, init_db, upsert_products, list_products, add_observations, latest_observations
from hardcore_bot.models import Product


def test_storage_roundtrip_and_bilingual_digest(tmp_path):
    db = tmp_path / "bot.sqlite3"
    con = connect(db)
    init_db(con)
    products = [Product("pepsi-2l", "Pepsi 2 л", "Pepsi 2 л", "beverages", "2 л")]
    upsert_products(con, products)
    add_observations(con, DemoCollector(datetime(2026, 6, 24, 12, 0)).collect(products))

    assert len(list_products(con)) == 1
    digest = format_digest(list_products(con), latest_observations(con), "ru")
    assert "Лучшие цены" in digest
    assert "KyivPrice" in digest


def test_format_products_contains_ids_for_watch_command():
    text = format_products([Product("eggs-c10", "Яйця", "Яйца", "staples", "10 шт")], "uk")
    assert "eggs-c10" in text
    assert "Доступні товари" in text
