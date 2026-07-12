from __future__ import annotations

from datetime import datetime
from typing import Iterable

from hardcore_bot.collectors.base import Collector
from hardcore_bot.models import PriceObservation, Product


class DemoCollector(Collector):
    name = "demo"

    def __init__(self, now: datetime | None = None) -> None:
        self.now = now or datetime.utcnow()

    def collect(self, products: Iterable[Product]) -> list[PriceObservation]:
        observations: list[PriceObservation] = []
        for idx, product in enumerate(products):
            base = 35.0 + idx * 12.5
            observations.extend([
                PriceObservation(product.id, "DemoMart", round(base, 2), self.now, True, f"https://example.invalid/{product.id}/demomart"),
                PriceObservation(product.id, "KyivPrice", round(base * 0.92, 2), self.now, True, f"https://example.invalid/{product.id}/kyivprice"),
                PriceObservation(product.id, "OutOfStock", round(base * 0.80, 2), self.now, False, None),
            ])
        return observations
