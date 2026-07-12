from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from typing import Any, Iterable

from hardcore_bot.collectors.base import Collector
from hardcore_bot.models import PriceObservation, Product


# Regex patterns for ATB product page HTML
_RE_PRICE = re.compile(
    r'<div\s[^>]*class="product-price[^"]*product-about__price"[^>]*>'
    r'(?:(?!</div>).)*?'
    r'<span>(\d+)\.<span\sclass="product-price__coin">(\d+)</span></span>',
    re.S,
)
_RE_OLD_PRICE = re.compile(
    r'<div\s[^>]*class="product-price[^"]*product-price--old[^"]*"[^>]*>'
    r'(?:(?!</div>).)*?'
    r'<span>(\d+)\.<span\sclass="product-price__coin">(\d+)</span></span>',
    re.S,
)
_RE_TITLE = re.compile(
    r'<h1\s[^>]*class="page-title[^"]*product-page__title"[^>]*>(.*?)</h1>',
    re.S,
)
_RE_ATTR = re.compile(r'(data-[\w-]+)="([^"]*)"')
_RE_DISCOUNT_LABEL = re.compile(
    r'Акція\s*до\s*([0-9]{1,2}\.[0-9]{1,2}\.(?:20)?\d{2})',
    re.I,
)
_RE_DISABLED_CLASS = re.compile(r'\bb-addToCart--disabled\b')


def parse_atb_product_page(html_content: str, source_url: str) -> dict[str, Any]:
    """Parse an ATB product page HTML into a provenance-rich data dict.

    Args:
        html_content: Raw HTML of an ATB product page.
        source_url: The URL the HTML was fetched from (used for
                    source_product_id extraction and record keeping).

    Returns:
        Dict with keys matching PriceObservation provenance fields:
            product_id (str, from data-productid)
            retailer (str, always "ATB")
            price_uah (float | None)
            available (bool)
            url (str, the source_url)
            source (str, always "atb")
            source_product_id (str | None, from data-productid)
            store_or_filial (str | None, from data-shopid)
            old_price_uah (float | None)
            discount_until (str | None, ISO date string if present)
            raw_json (str | None, compact JSON of data attrs)
            title (str | None, extracted product title)
    """
    result: dict[str, Any] = {
        "retailer": "ATB",
        "source": "atb",
        "url": source_url,
        "product_id": None,
        "price_uah": None,
        "available": True,
        "source_product_id": None,
        "store_or_filial": None,
        "old_price_uah": None,
        "discount_until": None,
        "raw_json": None,
        "title": None,
    }

    add_to_cart_match = re.search(
        r'<div\s[^>]*class="b-addToCart[^"]*"[^>]*>',
        html_content,
        re.S,
    )
    if add_to_cart_match:
        attrs_text = add_to_cart_match.group(0)
        attrs = dict(_RE_ATTR.findall(attrs_text))

        result["source_product_id"] = attrs.get("data-productid")
        result["store_or_filial"] = attrs.get("data-shopid")

        if _RE_DISABLED_CLASS.search(attrs_text):
            result["available"] = False

        if attrs:
            result["raw_json"] = json.dumps(attrs, separators=(",", ":"), ensure_ascii=False)

    title_match = _RE_TITLE.search(html_content)
    if title_match:
        result["title"] = html.unescape(title_match.group(1)).strip()

    price_match = _RE_PRICE.search(html_content)
    if price_match:
        integer_part = price_match.group(1)
        coin_part = price_match.group(2)
        result["price_uah"] = round(float(f"{integer_part}.{coin_part}"), 2)

    old_price_match = _RE_OLD_PRICE.search(html_content)
    if old_price_match:
        int_part = old_price_match.group(1)
        coin_part = old_price_match.group(2)
        result["old_price_uah"] = round(float(f"{int_part}.{coin_part}"), 2)

    discount_label_match = _RE_DISCOUNT_LABEL.search(html_content)
    if discount_label_match:
        date_str = discount_label_match.group(1)
        parts = date_str.split(".")
        day = parts[0].zfill(2)
        month = parts[1].zfill(2)
        year = parts[2] if len(parts[2]) == 4 else f"20{parts[2]}"
        result["discount_until"] = f"{year}-{month}-{day}"

    return result


def mapping_url_to_product_id(mappings: dict[str, Any]) -> dict[str, str]:
    """Build a lookup dict mapping normalized ATB URL -> product_id."""
    url_to_pid: dict[str, str] = {}
    for product in mappings.get("products", []):
        product_id = product.get("product_id")
        atb_map = (product.get("mappings") or {}).get("atb")
        if isinstance(product_id, str) and atb_map and "url" in atb_map:
            url = atb_map["url"].split("?")[0]
            url_to_pid[url] = product_id
    return url_to_pid


def mapping_product_id_to_url(mappings: dict[str, Any]) -> dict[str, str]:
    """Build a lookup dict mapping product_id -> normalized ATB URL."""
    pid_to_url: dict[str, str] = {}
    for product in mappings.get("products", []):
        product_id = product.get("product_id")
        atb_map = (product.get("mappings") or {}).get("atb")
        if isinstance(product_id, str) and atb_map and "url" in atb_map:
            pid_to_url[product_id] = atb_map["url"].split("?")[0]
    return pid_to_url


class AtbCollector(Collector):
    """Collector for exact ATB product-page mappings."""

    name = "atb"

    def __init__(
        self,
        mappings: dict[str, Any],
        now: datetime | None = None,
        session: Any | None = None,
    ) -> None:
        self.mappings = mappings
        self.now = now or datetime.now(timezone.utc).replace(tzinfo=None)
        self._session = session
        self._pid_to_url = mapping_product_id_to_url(mappings)

    def _get_session(self):
        if self._session is not None:
            return self._session
        import requests as req_lib

        s = req_lib.Session()
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "uk,en;q=0.8",
        })
        return s

    def collect(self, products: Iterable[Product]) -> list[PriceObservation]:
        observations: list[PriceObservation] = []
        session = self._get_session()

        for product in products:
            atb_url = self._pid_to_url.get(product.id)
            if atb_url is None:
                continue

            try:
                resp = session.get(atb_url, timeout=30)
                resp.raise_for_status()
                parsed = parse_atb_product_page(resp.text, atb_url)
            except Exception:
                observations.append(PriceObservation(
                    product_id=product.id,
                    retailer="ATB",
                    price_uah=0.0,
                    observed_at=self.now,
                    available=False,
                    url=atb_url,
                    source="atb",
                ))
                continue

            observations.append(PriceObservation(
                product_id=product.id,
                retailer=parsed["retailer"],
                price_uah=parsed["price_uah"] or 0.0,
                observed_at=self.now,
                available=parsed["available"],
                url=parsed["url"],
                source=parsed["source"],
                source_product_id=parsed["source_product_id"],
                store_or_filial=parsed["store_or_filial"],
                old_price_uah=parsed["old_price_uah"],
                discount_until=(
                    datetime.fromisoformat(parsed["discount_until"])
                    if parsed["discount_until"]
                    else None
                ),
                raw_json=parsed["raw_json"],
            ))

        return observations
