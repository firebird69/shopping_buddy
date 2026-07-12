"""Fixture-backed tests for ATB collector parsing.

Uses saved HTML fixtures from tests/fixtures/atb/ — no live HTTP.
"""

from pathlib import Path

from hardcore_bot.collectors.atb import (
    AtbCollector,
    mapping_product_id_to_url,
    mapping_url_to_product_id,
    parse_atb_product_page,
)

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures" / "atb"

# Source URLs corresponding to each fixture
URL_PEPSI = "https://www.atbmarket.com/product/napij-2-l-pepsi-black-bezalkogolnij-silnogazovanij"
URL_MUESLI = "https://www.atbmarket.com/product/suhi-snidanki-330-g-aha-musli-hrustki-fruktovi-z-medom-mup"
URL_SMETANA = "https://www.atbmarket.com/product/smetana-300-g-president-15-pstakan"
URL_MILK = "https://www.atbmarket.com/product/moloko-09-kg-agotinske-ultrapasterizovane-26"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_pepsi_price_and_provenance():
    """Normal in-stock product: price, product ID, store, brand extracted."""
    html = _load("pepsi_black_2l.html")
    result = parse_atb_product_page(html, URL_PEPSI)

    assert result["price_uah"] == 64.00
    assert result["available"] is True
    assert result["retailer"] == "ATB"
    assert result["source"] == "atb"
    assert result["url"] == URL_PEPSI
    assert result["source_product_id"] == "169778"
    assert result["store_or_filial"] == "101332"
    assert result["title"] == "Напій 2 л Pepsi Black безалкогольний сильногазований"
    assert result["old_price_uah"] is None
    assert result["discount_until"] is None
    assert result["raw_json"] is not None
    assert '"data-productid":"169778"' in result["raw_json"]


def test_parse_muesli_title_and_brand():
    """Normal in-stock product: correct title and product ID."""
    html = _load("aha_muesli_330g.html")
    result = parse_atb_product_page(html, URL_MUESLI)

    assert result["price_uah"] == 94.50
    assert result["available"] is True
    assert result["source_product_id"] == "185230"
    assert "АХА" in result["title"]
    assert result["old_price_uah"] is None
    assert result["discount_until"] is None


def test_parse_unavailable_product():
    """Out-of-stock product: available=False, price still extracted."""
    html = _load("president_smetana_300g.html")
    result = parse_atb_product_page(html, URL_SMETANA)

    assert result["available"] is False
    assert result["price_uah"] == 59.30
    assert result["source_product_id"] == "188992"
    assert "President" in result["title"]
    assert result["old_price_uah"] is None


def test_parse_promo_product():
    """Product on promo: old_price_uah and discount_until extracted."""
    html = _load("yagotynske_milk_900g.html")
    result = parse_atb_product_page(html, URL_MILK)

    assert result["price_uah"] == 44.90
    assert result["available"] is True
    assert result["source_product_id"] == "167518"
    assert result["old_price_uah"] == 60.20
    assert result["discount_until"] == "2026-07-31"
    assert "Яготинське" in result["title"]


def test_parse_invalid_html():
    """Empty or invalid HTML returns None fields without crashing."""
    result = parse_atb_product_page("", "https://example.com")
    assert result["price_uah"] is None
    assert result["available"] is True
    assert result["source_product_id"] is None
    assert result["old_price_uah"] is None

    result2 = parse_atb_product_page("<html><body>no data</body></html>", "https://example.com")
    assert result2["price_uah"] is None
    assert result2["source_product_id"] is None


def test_mapping_url_to_product_id():
    """mapping_url_to_product_id builds correct url->pid lookup."""
    mappings = {
        "version": 1,
        "products": [
            {
                "product_id": "pepsi-black-2l",
                "mappings": {
                    "atb": {
                        "url": "https://www.atbmarket.com/product/napij-2-l-pepsi-black-bezalkogolnij-silnogazovanij",
                    },
                },
            },
            {
                "product_id": "aha-fruit-honey-muesli-330g",
                "mappings": {
                    "atb": {
                        "url": "https://www.atbmarket.com/product/suhi-snidanki-330-g-aha-musli-hrustki-fruktovi-z-medom-mup",
                    },
                },
            },
        ],
    }
    lookup = mapping_url_to_product_id(mappings)
    assert lookup["https://www.atbmarket.com/product/napij-2-l-pepsi-black-bezalkogolnij-silnogazovanij"] == "pepsi-black-2l"
    assert lookup["https://www.atbmarket.com/product/suhi-snidanki-330-g-aha-musli-hrustki-fruktovi-z-medom-mup"] == "aha-fruit-honey-muesli-330g"
    assert "nonexistent" not in lookup


def test_mapping_url_to_product_id_strips_query_params():
    """URLs with query params are normalized by stripping ?... for matching."""
    mappings = {
        "version": 1,
        "products": [
            {
                "product_id": "president-smetana-15-300g",
                "mappings": {
                    "atb": {
                        "url": "https://www.atbmarket.com/product/smetana-300-g-president-15-pstakan?query=%D1%81%D0%BC%D0%B5%D1%82%D0%B0%D0%BD%D0%B0",
                    },
                },
            },
        ],
    }
    lookup = mapping_url_to_product_id(mappings)
    assert "https://www.atbmarket.com/product/smetana-300-g-president-15-pstakan" in lookup
    assert lookup["https://www.atbmarket.com/product/smetana-300-g-president-15-pstakan"] == "president-smetana-15-300g"


def test_mapping_product_id_to_url_strips_query_params():
    """Collector lookup maps product IDs to normalized exact ATB URLs."""
    mappings = {
        "version": 1,
        "products": [
            {
                "product_id": "president-smetana-15-300g",
                "mappings": {
                    "atb": {
                        "url": "https://www.atbmarket.com/product/smetana-300-g-president-15-pstakan?query=smetana",
                    },
                },
            },
        ],
    }

    lookup = mapping_product_id_to_url(mappings)
    assert lookup == {
        "president-smetana-15-300g": "https://www.atbmarket.com/product/smetana-300-g-president-15-pstakan",
    }


def test_collector_uses_mappings(tmp_path):
    """AtbCollector.collect() resolves mappings and returns PriceObservations.

    Uses a mock session that returns fixture content.
    """
    from datetime import datetime
    from unittest.mock import Mock

    from hardcore_bot.models import Product

    mappings = {
        "version": 1,
        "products": [
            {
                "product_id": "pepsi-black-2l",
                "mappings": {
                    "atb": {"url": URL_PEPSI},
                },
            },
            {
                "product_id": "president-smetana-15-300g",
                "mappings": {
                    "atb": {
                        "url": "https://www.atbmarket.com/product/smetana-300-g-president-15-pstakan?query=smetana",
                    },
                },
            },
        ],
    }

    mock_responses = {
        URL_PEPSI: _load("pepsi_black_2l.html"),
        "https://www.atbmarket.com/product/smetana-300-g-president-15-pstakan": _load(
            "president_smetana_300g.html"
        ),
    }

    def mock_get(url, **kwargs):
        mock_resp = Mock()
        mock_resp.status_code = 200
        base_url = url.split("?")[0]
        mock_resp.text = mock_responses.get(base_url, "")
        mock_resp.raise_for_status.return_value = None
        return mock_resp

    session = Mock()
    session.get = mock_get

    collector = AtbCollector(mappings, now=datetime(2026, 7, 12, 12, 0), session=session)
    products = [
        Product("pepsi-black-2l", "Test", "Test", "beverages", "2 л"),
        Product("president-smetana-15-300g", "Test", "Test", "dairy", "300 г"),
    ]
    obs = collector.collect(products)

    assert len(obs) == 2

    pepsi_obs = [o for o in obs if o.product_id == "pepsi-black-2l"][0]
    assert pepsi_obs.price_uah == 64.00
    assert pepsi_obs.available is True
    assert pepsi_obs.retailer == "ATB"
    assert pepsi_obs.source == "atb"
    assert pepsi_obs.source_product_id == "169778"
    assert pepsi_obs.old_price_uah is None

    smetana_obs = [o for o in obs if o.product_id == "president-smetana-15-300g"][0]
    assert smetana_obs.available is False
    assert smetana_obs.price_uah == 59.30
    assert smetana_obs.source_product_id == "188992"
