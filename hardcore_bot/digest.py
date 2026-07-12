from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from .models import PriceObservation, Product


@dataclass(frozen=True)
class PriceEntry:
    """One store's price for a product in the daily digest."""
    retailer: str
    price_uah: float | None  # None = unavailable or missing
    available: bool
    source: str | None
    url: str | None
    is_best: bool = False


@dataclass(frozen=True)
class DigestEntry:
    """One product's digest block containing prices from covered stores."""
    product: Product
    price_entries: list[PriceEntry] = field(default_factory=list)


def group_latest_by_product(
    observations: Sequence[PriceObservation],
) -> dict[str, list[PriceObservation]]:
    """Group the latest observation per (product_id, retailer).

    Input are the latest observations per product/retailer pair
    (as returned by storage.latest_observations()). Returns a dict
    mapping product_id -> list of observations sorted by price ASC
    (best/cheapest available first).
    """
    groups: dict[str, list[PriceObservation]] = {}
    for obs in observations:
        groups.setdefault(obs.product_id, []).append(obs)
    # Sort each group: available before unavailable, then price ASC
    for pid in groups:
        groups[pid].sort(key=lambda o: (0 if o.available else 1, o.price_uah if o.available else float("inf")))
    return groups


def build_digest_entries(
    products: Sequence[Product],
    observations: Sequence[PriceObservation],
    covered_sources: Sequence[str] | None = None,
    watched_ids: set[str] | None = None,
) -> list[DigestEntry]:
    """Build structured digest data for the daily contact.

    Args:
        products: All known products (used for titles/display).
        observations: Latest observations per product/retailer (typically
                      from storage.latest_observations()).
        covered_sources: Ordered list of source names to include. Observations
                         from unmatched sources are still included but may
                         appear at the end.
        watched_ids: If set, only include these product IDs. If None, include
                     all products that have observations.

    Returns:
        List of DigestEntry, one per product, sorted by product ID.
        Within each entry, available prices are sorted cheapest first,
        followed by unavailable entries.
    """
    product_map = {p.id: p for p in products}
    grouped = group_latest_by_product(observations)

    result: list[DigestEntry] = []

    # Determine which product IDs to include. When explicit watched IDs are
    # provided, include them even if there are no observations yet so the daily
    # digest can show covered stores as missing/unavailable instead of silently
    # hiding a watched SKU.
    if watched_ids is not None:
        pids = watched_ids
    else:
        pids = set(grouped.keys())

    for pid in sorted(pids):
        product = product_map.get(pid)
        if product is None:
            continue
        group = grouped.get(pid, [])
        entries = _build_price_entries(group, covered_sources)
        result.append(DigestEntry(product=product, price_entries=entries))

    return result


def _build_price_entries(
    group: list[PriceObservation],
    covered_sources: Sequence[str] | None,
) -> list[PriceEntry]:
    """Build PriceEntry list with best-price-first ordering and coverage markers.

    The best available price (cheapest) gets is_best=True.
    All stores that appear in covered_sources but have no observation
    are appended as unavailable entries at the end.
    """
    entries: list[PriceEntry] = []

    # Separate available and unavailable
    available = [o for o in group if o.available]
    unavailable = [o for o in group if not o.available]

    # Sort available by price ASC
    available.sort(key=lambda o: o.price_uah)

    # Mark the best (cheapest available)
    for i, obs in enumerate(available):
        entries.append(PriceEntry(
            retailer=obs.retailer,
            price_uah=obs.price_uah,
            available=True,
            source=obs.source,
            url=obs.url,
            is_best=(i == 0),
        ))

    # Add unavailable observations
    for obs in unavailable:
        entries.append(PriceEntry(
            retailer=obs.retailer,
            price_uah=obs.price_uah,
            available=False,
            source=obs.source,
            url=obs.url,
        ))

    # Add missing covered stores (sources with no observation at all)
    if covered_sources is not None:
        covered = set(covered_sources)
        # Distinguish between retailer and source — for now use retailer
        # as the key (most common case); fallback to source field.
        observed_retailers = {o.retailer for o in group}
        observed_sources = {o.source for o in group if o.source}
        for src in covered_sources:
            if src not in observed_retailers and src not in observed_sources:
                entries.append(PriceEntry(
                    retailer=src,
                    price_uah=None,
                    available=False,
                    source=src,
                    url=None,
                ))

    return entries
