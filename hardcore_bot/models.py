from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class Product:
    id: str
    title_uk: str
    title_ru: str
    category: str
    size: str


@dataclass(frozen=True)
class PriceObservation:
    product_id: str
    retailer: str
    price_uah: float
    observed_at: datetime
    available: bool = True
    url: Optional[str] = None
    # Source provenance (added MVP slice 2026-07-12)
    source: Optional[str] = None  # e.g. "atb", "fora", "thrash", "auchan", "novus"
    source_product_id: Optional[str] = None  # source-native product identifier
    store_or_filial: Optional[str] = None  # store/filial location context
    old_price_uah: Optional[float] = None  # crossed-out price if on promo
    discount_until: Optional[datetime] = None  # promo validity end date
    raw_json: Optional[str] = None  # raw source payload for debugging


@dataclass(frozen=True)
class WatchRule:
    user_id: int
    product_id: str
    drop_percent: float = 15.0
    threshold_uah: Optional[float] = None
    best_today: bool = True
    cooldown_hours: int = 24


@dataclass(frozen=True)
class AlertCandidate:
    user_id: int
    product_id: str
    retailer: str
    price_uah: float
    reason: str
    lang: str = "uk"
    url: Optional[str] = None
