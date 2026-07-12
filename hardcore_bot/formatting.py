from __future__ import annotations

from .i18n import t, normalize_lang
from .models import Product, PriceObservation, AlertCandidate
from .alerts import reason_kind


def product_title(product: Product, lang: str) -> str:
    return product.title_ru if normalize_lang(lang) == "ru" else product.title_uk


def format_products(products: list[Product], lang: str = "uk") -> str:
    lines = [t("products_header", lang)]
    for p in products:
        lines.append(f"• `{p.id}` — {product_title(p, lang)} ({p.size})")
    return "\n".join(lines)


def format_digest(products: list[Product], observations: list[PriceObservation], lang: str = "uk") -> str:
    by_id = {p.id: p for p in products}
    best: dict[str, PriceObservation] = {}
    for obs in observations:
        if not obs.available:
            continue
        current = best.get(obs.product_id)
        if current is None or obs.price_uah < current.price_uah:
            best[obs.product_id] = obs
    lines = [t("digest_header", lang)]
    for pid, obs in sorted(best.items()):
        product = by_id.get(pid)
        title = product_title(product, lang) if product else pid
        lines.append(f"• {title}: {obs.price_uah:.2f} грн — {obs.retailer}")
    return "\n".join(lines)


def format_alert(alert: AlertCandidate, product: Product, lang: str = "uk") -> str:
    kind = reason_kind(alert.reason)
    title = product_title(product, lang)
    if kind == "drop":
        drop = float(alert.reason.split(":", 1)[1]) if ":" in alert.reason else 0.0
        return t("alert_drop", lang, product=title, price=alert.price_uah, retailer=alert.retailer, drop=drop)
    if kind == "threshold":
        return t("alert_threshold", lang, product=title, price=alert.price_uah, retailer=alert.retailer)
    return t("alert_best", lang, product=title, price=alert.price_uah, retailer=alert.retailer)
