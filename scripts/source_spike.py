#!/usr/bin/env python3
"""Low-volume source/channel feasibility and event-coverage script.

This script is intentionally small enough to operate before a full production
collector exists, but structured enough to answer the go/no-go question:

- can the current public sources return useful promo/price data now?
- are promo end dates good enough for target event windows?
- can we add channels/sources without rewriting the whole script?

Adding a new channel that uses an existing source type is data-only: pass a JSON
config via --channel-config. Adding a brand-new protocol still requires one new
fetch_* function plus one REGISTRY entry.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "source_spikes"
UA = "Mozilla/5.0 source-feasibility-spike/0.2 (+low-volume pre-MVP check)"
TIMEOUT = 30
MAX_PER_SOURCE = 5


@dataclass(frozen=True)
class Channel:
    """One configured source/channel to fetch.

    kind selects the fetcher implementation. params let us vary retailer URLs,
    search terms, filial/store IDs, limits, and similar knobs without editing the
    script for every new channel.
    """

    name: str
    kind: str
    retailer: str
    enabled: bool = True
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class SpikeItem:
    source: str
    retailer: str
    store_or_filial: str | None
    source_product_id: str | None
    sku: str | None
    ean: str | None
    title: str | None
    price_uah: float | None
    old_price_uah: float | None
    discount_percent: float | None
    discount_until: str | None
    in_stock_or_available: bool | None
    category: str | None
    source_url: str | None
    fetched_at: str
    raw: dict[str, Any]


@dataclass
class EventAssessment:
    target_date: str
    active_promos: int = 0
    unknown_dated_promos: int = 0
    expired_or_not_covering: int = 0
    sample_titles: list[str] = field(default_factory=list)


DEFAULT_CHANNELS = [
    Channel("atb_homepage", "atb_homepage", "ATB", params={"url": "https://www.atbmarket.com/"}),
    Channel(
        "auchan_official_milk",
        "auchan_graphql_search",
        "Auchan",
        params={"url": "https://auchan.ua/graphql", "search": "молоко", "store": "ua"},
    ),
    Channel("zakaz_novus_home", "zakaz_next_data", "Novus via Zakaz", params={"url": "https://novus.zakaz.ua/en/"}),
    Channel(
        "fora_milk_filial_310",
        "fora_catalog_search",
        "Fora",
        params={"search": "молоко", "filialId": 310, "merchantId": 2, "deliveryType": 2},
    ),
    Channel("thrash_active_offers", "thrash_offers", "THRASH!ТРАШ!", params={"pageSlug": "main"}),
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "uk,en;q=0.8"})
    return s


def money(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def zakaz_minor(value: Any) -> float | None:
    try:
        return round(float(value) / 100.0, 2)
    except (TypeError, ValueError):
        return None


def clean_text(value: str | None) -> str | None:
    if not value:
        return None
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value or None


def extract_next_data(text: str) -> dict[str, Any]:
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', text, re.S)
    if not m:
        raise ValueError("__NEXT_DATA__ not found")
    return json.loads(m.group(1))


def walk_dicts(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk_dicts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_dicts(v)


def channel_limit(channel: Channel) -> int:
    return int(channel.params.get("limit", MAX_PER_SOURCE))


def parse_date_token(token: str, fetched_year: int) -> date | None:
    token = token.strip()
    if not token:
        return None
    token = token.replace("/", ".")
    iso_match = re.search(r"(20\d{2})-(\d{2})-(\d{2})", token)
    if iso_match:
        return date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
    dotted = re.search(r"\b(\d{1,2})\.(\d{1,2})(?:\.(20\d{2}))?\b", token)
    if dotted:
        day = int(dotted.group(1))
        month = int(dotted.group(2))
        year = int(dotted.group(3) or fetched_year)
        return date(year, month, day)
    return None


def parse_discount_until(value: str | None, fetched_at: str) -> date | None:
    if not value:
        return None
    try:
        fetched_year = datetime.fromisoformat(fetched_at.replace("Z", "+00:00")).year
    except ValueError:
        fetched_year = datetime.now(timezone.utc).year
    return parse_date_token(value, fetched_year)


def has_discount(item: SpikeItem) -> bool:
    return bool(
        (item.old_price_uah is not None and item.price_uah is not None and item.old_price_uah > item.price_uah)
        or (item.discount_percent is not None and item.discount_percent > 0)
    )


def assess_events(items: list[SpikeItem], targets: list[date]) -> dict[str, EventAssessment]:
    assessments = {t.isoformat(): EventAssessment(t.isoformat()) for t in targets}
    for item in items:
        if not has_discount(item):
            continue
        until = parse_discount_until(item.discount_until, item.fetched_at)
        for target in targets:
            assessment = assessments[target.isoformat()]
            if until is None:
                assessment.unknown_dated_promos += 1
            elif until >= target:
                assessment.active_promos += 1
                if len(assessment.sample_titles) < 5 and item.title:
                    assessment.sample_titles.append(f"{item.retailer}: {item.title} (until {item.discount_until})")
            else:
                assessment.expired_or_not_covering += 1
    return assessments


def fetch_atb(s: requests.Session, fetched_at: str, channel: Channel) -> tuple[list[SpikeItem], dict[str, Any]]:
    url = channel.params.get("url", "https://www.atbmarket.com/")
    r = s.get(url, timeout=TIMEOUT)
    evidence = {"url": url, "status": r.status_code, "bytes": len(r.text), "cloudflare_marker": "cloudflare" in r.text.lower() or "cf-chl" in r.text.lower()}
    r.raise_for_status()
    text = r.text
    items: list[SpikeItem] = []
    for m in re.finditer(r'<div class="b-addToCart"(?P<attrs>[^>]+)>', text, re.I):
        if len(items) >= channel_limit(channel):
            break
        start = max(0, m.start() - 2600)
        chunk = text[start:m.end()]
        attrs = dict(re.findall(r'(data-[\w-]+)="([^"]*)"', m.group("attrs")))
        title_m = re.search(r'<div class="sale-slide__name"><a href="([^"]+)">(.*?)</a>', chunk, re.S)
        old_m = re.search(r'sale-slide__old-price"><span>(\d+)\.<span class="product-price__coin">(\d+)</span>', chunk, re.S)
        new_m = re.search(r'sale-slide__new-price"><span>(\d+)\.<span class="product-price__coin">(\d+)</span>', chunk, re.S)
        until_m = re.search(r'Дія акції до:\s*</span>\s*([0-9.]+)', chunk)
        label_m = re.search(r'sale-slide__label">\s*-?([0-9]+)%', chunk)
        product_url = None
        title = None
        if title_m:
            product_url = "https://www.atbmarket.com" + html.unescape(title_m.group(1))
            title = clean_text(title_m.group(2))
        items.append(SpikeItem(
            source=channel.name,
            retailer=channel.retailer,
            store_or_filial=attrs.get("data-shopid"),
            source_product_id=attrs.get("data-productid"),
            sku=None,
            ean=None,
            title=title,
            price_uah=money(f"{new_m.group(1)}.{new_m.group(2)}") if new_m else None,
            old_price_uah=money(f"{old_m.group(1)}.{old_m.group(2)}") if old_m else None,
            discount_percent=money(label_m.group(1)) if label_m else None,
            discount_until=until_m.group(1) if until_m else None,
            in_stock_or_available=True,
            category=attrs.get("data-category"),
            source_url=product_url or url,
            fetched_at=fetched_at,
            raw={"attrs": attrs, "kind": channel.kind},
        ))
    evidence["items"] = len(items)
    return items, evidence


def fetch_auchan_official(s: requests.Session, fetched_at: str, channel: Channel) -> tuple[list[SpikeItem], dict[str, Any]]:
    url = channel.params.get("url", "https://auchan.ua/graphql")
    search = channel.params.get("search", "молоко")
    query = """
    query SourceSpike($search: String!, $pageSize: Int!) {
      products(search: $search, pageSize: $pageSize) {
        total_count
        items {
          sku
          name
          url_key
          stock_status
          price_range {
            minimum_price {
              regular_price { value currency }
              final_price { value currency }
              discount { amount_off percent_off }
            }
          }
          categories { name url_path }
        }
      }
    }
    """
    r = s.post(
        url,
        json={"query": query, "variables": {"search": search, "pageSize": channel_limit(channel)}},
        headers={"Content-Type": "application/json", "Store": channel.params.get("store", "ua"), "Accept": "application/json"},
        timeout=TIMEOUT,
    )
    evidence = {"url": url, "status": r.status_code, "bytes": len(r.text), "search": search}
    r.raise_for_status()
    data = r.json()
    products = (data.get("data") or {}).get("products") or {}
    evidence["total_count"] = products.get("total_count")
    items: list[SpikeItem] = []
    for p in (products.get("items") or [])[: channel_limit(channel)]:
        price = (((p.get("price_range") or {}).get("minimum_price") or {}))
        regular = (price.get("regular_price") or {})
        final = (price.get("final_price") or {})
        discount = price.get("discount") or {}
        cats = p.get("categories") or []
        items.append(SpikeItem(
            source=channel.name,
            retailer=channel.retailer,
            store_or_filial=channel.params.get("store"),
            source_product_id=p.get("sku"),
            sku=p.get("sku"),
            ean=None,
            title=p.get("name"),
            price_uah=money(final.get("value")),
            old_price_uah=money(regular.get("value")) if regular.get("value") != final.get("value") else None,
            discount_percent=money(discount.get("percent_off")),
            discount_until=None,
            in_stock_or_available=(p.get("stock_status") == "IN_STOCK"),
            category=(cats[-1].get("name") if cats else None),
            source_url=("https://auchan.ua/ua/" + p.get("url_key") + "/") if p.get("url_key") else "https://auchan.ua/",
            fetched_at=fetched_at,
            raw={"stock_status": p.get("stock_status"), "kind": channel.kind},
        ))
    evidence["items"] = len(items)
    return items, evidence


def fetch_zakaz_next_data(s: requests.Session, fetched_at: str, channel: Channel) -> tuple[list[SpikeItem], dict[str, Any]]:
    url = channel.params.get("url")
    if not url:
        raise ValueError("zakaz_next_data channel requires params.url")
    r = s.get(url, timeout=TIMEOUT)
    evidence = {"url": url, "status": r.status_code, "bytes": len(r.text), "cloudflare_marker": "cloudflare" in r.text.lower() or "cf-chl" in r.text.lower()}
    r.raise_for_status()
    data = extract_next_data(r.text)
    products = []
    seen = set()
    for d in walk_dicts(data):
        if "title" in d and "price" in d and ("sku" in d or "ean" in d):
            key = d.get("sku") or d.get("ean") or d.get("title")
            if key in seen:
                continue
            seen.add(key)
            products.append(d)
            if len(products) >= channel_limit(channel):
                break
    items: list[SpikeItem] = []
    for p in products:
        disc = p.get("discount") or {}
        items.append(SpikeItem(
            source=channel.name,
            retailer=channel.retailer,
            store_or_filial=channel.params.get("store_or_filial"),
            source_product_id=p.get("sku"),
            sku=p.get("sku"),
            ean=p.get("ean"),
            title=p.get("title"),
            price_uah=zakaz_minor(p.get("price")),
            old_price_uah=zakaz_minor(disc.get("old_price")),
            discount_percent=money(disc.get("value")),
            discount_until=disc.get("due_date"),
            in_stock_or_available=p.get("in_stock"),
            category=None,
            source_url=url,
            fetched_at=fetched_at,
            raw={"unit": p.get("unit"), "currency": p.get("currency"), "kind": channel.kind},
        ))
    evidence["items"] = len(items)
    return items, evidence


def fetch_thrash(s: requests.Session, fetched_at: str, channel: Channel) -> tuple[list[SpikeItem], dict[str, Any]]:
    url = channel.params.get("url", "https://thrash.ua/graphql")
    query = """
    query offers($categoryId: ID, $filialIds: [ID], $coordinates: Coordinates, $pagingInfo: InputBatch!, $pageSlug: String!, $random: Boolean!, $onlyActive: Boolean) {
      offersSplited(categoryId: $categoryId, filialIds: $filialIds, coordinates: $coordinates, pagingInfo: $pagingInfo, pageSlug: $pageSlug, random: $random, onlyActive: $onlyActive) {
        products { count items { ... on Product { id slug articul title weight available price oldPrice discountPercent activePeriod { start end } category { title } } } }
      }
    }
    """
    payload = {
        "operationName": "offers",
        "variables": {
            "categoryId": channel.params.get("categoryId"),
            "filialIds": channel.params.get("filialIds"),
            "coordinates": channel.params.get("coordinates"),
            "pagingInfo": {"offset": int(channel.params.get("offset", 0)), "limit": channel_limit(channel)},
            "onlyActive": True,
            "pageSlug": channel.params.get("pageSlug", "main"),
            "random": bool(channel.params.get("random", True)),
        },
        "query": query,
    }
    r = s.post(url, json=payload, headers={"Content-Type": "application/json", "Accept": "application/json"}, timeout=TIMEOUT)
    evidence = {"url": url, "status": r.status_code, "bytes": len(r.text)}
    r.raise_for_status()
    data = r.json()
    products = (((data.get("data") or {}).get("offersSplited") or {}).get("products") or {})
    evidence["total_count"] = products.get("count")
    items: list[SpikeItem] = []
    for p in (products.get("items") or [])[: channel_limit(channel)]:
        active = p.get("activePeriod") or {}
        cat = p.get("category") or {}
        slug = p.get("slug")
        items.append(SpikeItem(
            source=channel.name,
            retailer=channel.retailer,
            store_or_filial=None,
            source_product_id=str(p.get("id")) if p.get("id") is not None else None,
            sku=str(p.get("articul")) if p.get("articul") is not None else None,
            ean=None,
            title=p.get("title"),
            price_uah=money(p.get("price")),
            old_price_uah=money(p.get("oldPrice")),
            discount_percent=money(p.get("discountPercent")),
            discount_until=active.get("end"),
            in_stock_or_available=p.get("available"),
            category=cat.get("title") if isinstance(cat, dict) else None,
            source_url=("https://thrash.ua/product/" + slug) if slug else "https://thrash.ua/",
            fetched_at=fetched_at,
            raw={"weight": p.get("weight"), "active_start": active.get("start"), "kind": channel.kind},
        ))
    evidence["items"] = len(items)
    return items, evidence


def fetch_fora(s: requests.Session, fetched_at: str, channel: Channel) -> tuple[list[SpikeItem], dict[str, Any]]:
    url = channel.params.get("url", "https://api.catalog.ecom.fora.ua/api/2.0/exec/EcomCatalogGlobal")
    payload = {
        "method": channel.params.get("method", "GetSimpleCatalogItems"),
        "data": {
            "customFilter": channel.params.get("search", "молоко"),
            "deliveryType": channel.params.get("deliveryType", 2),
            "filialId": channel.params.get("filialId", 310),
            "merchantId": channel.params.get("merchantId", 2),
            "page": channel.params.get("page", 1),
            "limit": channel_limit(channel),
        },
    }
    r = s.post(url, json=payload, headers={"Content-Type": "application/json", "Accept": "application/json"}, timeout=TIMEOUT)
    evidence = {"url": url, "status": r.status_code, "bytes": len(r.text), "note": "Public replay attempt without persisted browser JWT/cookies", "search": payload["data"]["customFilter"]}
    if r.status_code >= 400:
        evidence["error_sample"] = r.text[:500]
        return [], evidence
    data = r.json()
    raw_items = []
    for d in walk_dicts(data):
        if isinstance(d, dict) and ("name" in d or "title" in d) and ("price" in d or "oldPrice" in d):
            raw_items.append(d)
            if len(raw_items) >= channel_limit(channel):
                break
    items: list[SpikeItem] = []
    for p in raw_items:
        promo = p.get("promotion") or {}
        items.append(SpikeItem(
            source=channel.name,
            retailer=channel.retailer,
            store_or_filial=str(channel.params.get("filialId", "")) or None,
            source_product_id=str(p.get("id")) if p.get("id") is not None else None,
            sku=str(p.get("sku")) if p.get("sku") is not None else None,
            ean=str(p.get("barcode")) if p.get("barcode") is not None else None,
            title=p.get("name") or p.get("title"),
            price_uah=money(p.get("price")),
            old_price_uah=money(p.get("oldPrice")),
            discount_percent=None,
            discount_until=promo.get("stopAfter") or promo.get("endDate"),
            in_stock_or_available=p.get("available"),
            category=None,
            source_url="https://fora.ua/",
            fetched_at=fetched_at,
            raw={"unit": p.get("unit"), "promotion": promo, "kind": channel.kind},
        ))
    evidence["items"] = len(items)
    return items, evidence


Fetcher = Callable[[requests.Session, str, Channel], tuple[list[SpikeItem], dict[str, Any]]]
REGISTRY: dict[str, Fetcher] = {
    "atb_homepage": fetch_atb,
    "auchan_graphql_search": fetch_auchan_official,
    "zakaz_next_data": fetch_zakaz_next_data,
    "fora_catalog_search": fetch_fora,
    "thrash_offers": fetch_thrash,
}


def load_channels(config_path: str | None) -> list[Channel]:
    if not config_path:
        return list(DEFAULT_CHANNELS)
    data = json.loads(Path(config_path).read_text(encoding="utf-8"))
    raw_channels = data.get("channels", data if isinstance(data, list) else [])
    channels = []
    for raw in raw_channels:
        channels.append(Channel(
            name=raw["name"],
            kind=raw["kind"],
            retailer=raw.get("retailer", raw["name"]),
            enabled=raw.get("enabled", True),
            params=raw.get("params", {}),
        ))
    return channels


def parse_targets(values: list[str]) -> list[date]:
    targets: list[date] = []
    for value in values:
        for part in value.split(","):
            part = part.strip()
            if not part:
                continue
            if ".." in part:
                start_s, end_s = part.split("..", 1)
                start = date.fromisoformat(start_s)
                end = date.fromisoformat(end_s)
                delta = (end - start).days
                if delta < 0:
                    raise ValueError(f"target date window ends before it starts: {part}")
                targets.extend(date.fromordinal(start.toordinal() + i) for i in range(delta + 1))
            else:
                targets.append(date.fromisoformat(part))
    return sorted(set(targets))


def selected_channels(channels: list[Channel], names: str | None) -> list[Channel]:
    enabled = [c for c in channels if c.enabled]
    if not names:
        return enabled
    wanted = {n.strip() for n in names.split(",") if n.strip()}
    selected = [c for c in enabled if c.name in wanted]
    missing = wanted - {c.name for c in selected}
    if missing:
        raise ValueError(f"unknown or disabled channel(s): {', '.join(sorted(missing))}")
    return selected


def run(label: str, channels: list[Channel], targets: list[date]) -> tuple[Path, Path, dict[str, Any]]:
    fetched_at = now_iso()
    s = session()
    all_items: list[SpikeItem] = []
    evidence: dict[str, Any] = {"label": label, "fetched_at": fetched_at, "channels": {}, "target_dates": [t.isoformat() for t in targets]}
    for channel in channels:
        fn = REGISTRY.get(channel.kind)
        if not fn:
            evidence["channels"][channel.name] = {"ok": False, "error": f"unsupported channel kind: {channel.kind}"}
            continue
        try:
            items, ev = fn(s, fetched_at, channel)
            all_items.extend(items)
            evidence["channels"][channel.name] = {**ev, "kind": channel.kind, "retailer": channel.retailer, "ok": bool(items)}
        except Exception as exc:  # evidence spike: keep going across channels
            evidence["channels"][channel.name] = {"ok": False, "kind": channel.kind, "retailer": channel.retailer, "error": f"{type(exc).__name__}: {exc}"}
    event_assessments = assess_events(all_items, targets) if targets else {}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = OUT_DIR / f"source_spike_{label}_{stamp}.json"
    report_path = OUT_DIR / f"source_spike_{label}_{stamp}.md"
    payload = {
        "label": label,
        "fetched_at": fetched_at,
        "evidence": evidence,
        "event_assessments": {k: asdict(v) for k, v in event_assessments.items()},
        "items": [asdict(i) for i in all_items],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    ok_channels = sum(1 for ev in evidence["channels"].values() if ev.get("ok"))
    total_channels = len(evidence["channels"])
    lines = [
        f"# Source/channel spike {label} — {fetched_at}",
        "",
        "## Verdict signal",
        "",
        f"- Live channels with items: **{ok_channels}/{total_channels}**.",
        f"- Normalized items: **{len(all_items)}**.",
        "- Good-enough threshold for target-event monitoring: at least 3 live channels and at least one dated promo covering each target date, or an explicit operator decision to accept unknown-dated discounts.",
        "",
        "## Channel summary",
        "",
        "| Channel | Kind | Retailer | OK | Items | Evidence |",
        "|---|---|---|---:|---:|---|",
    ]
    for name, ev in evidence["channels"].items():
        lines.append(
            f"| {name} | {ev.get('kind', '-')} | {ev.get('retailer', '-')} | {'yes' if ev.get('ok') else 'no'} | {ev.get('items', 0)} | status={ev.get('status', '-')}; bytes={ev.get('bytes', '-')}; {ev.get('error', ev.get('note', ''))} |"
        )
    if targets:
        lines += ["", "## Target event/date coverage", "", "| Target date | Active dated promos | Unknown-dated discounts | Expired/not covering | Samples |", "|---|---:|---:|---:|---|"]
        for target in targets:
            ass = event_assessments[target.isoformat()]
            samples = "<br>".join(ass.sample_titles) if ass.sample_titles else "-"
            lines.append(f"| {ass.target_date} | {ass.active_promos} | {ass.unknown_dated_promos} | {ass.expired_or_not_covering} | {samples} |")
    lines += ["", "## Normalized items", ""]
    for item in all_items:
        until = f"; until {item.discount_until}" if item.discount_until else ""
        lines.append(
            f"- **{item.retailer}** / `{item.source}` / `{item.source_product_id or item.sku or '-'}` — {item.title} — {item.price_uah} UAH"
            + (f" (old {item.old_price_uah})" if item.old_price_uah else "")
            + until
        )
    lines += [
        "",
        "## Adding channels",
        "",
        "Use `--channel-config channels.json`. Config shape:",
        "",
        "```json",
        json.dumps({"channels": [asdict(DEFAULT_CHANNELS[1])]}, ensure_ascii=False, indent=2),
        "```",
        "",
        "Supported `kind` values now: " + ", ".join(sorted(REGISTRY)),
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path, payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Low-volume source/channel spike for The Hardcore Bot")
    parser.add_argument("--label", default="pass")
    parser.add_argument("--channel-config", help="JSON file with channels[]; use this to add/disable/reparameterize sources")
    parser.add_argument("--sources", help="Comma-separated channel names to run; defaults to all enabled channels")
    parser.add_argument("--target-date", action="append", default=[], help="Target event date(s), e.g. 2026-07-01 or 2026-07-01..2026-07-02. Can be repeated or comma-separated.")
    args = parser.parse_args(argv)

    channels = selected_channels(load_channels(args.channel_config), args.sources)
    targets = parse_targets(args.target_date)
    json_path, report_path, payload = run(args.label, channels, targets)
    print(f"json={json_path}")
    print(f"report={report_path}")
    for name, ev in payload["evidence"]["channels"].items():
        print(f"{name}: ok={ev.get('ok')} items={ev.get('items', 0)} status={ev.get('status', '-')} {ev.get('error', '')}")
    if payload.get("event_assessments"):
        for day, ass in payload["event_assessments"].items():
            print(f"target={day}: active_promos={ass['active_promos']} unknown_dated_discounts={ass['unknown_dated_promos']} expired_or_not_covering={ass['expired_or_not_covering']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
