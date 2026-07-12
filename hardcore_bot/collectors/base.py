from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from hardcore_bot.models import PriceObservation, Product


class Collector(ABC):
    name: str

    @abstractmethod
    def collect(self, products: Iterable[Product]) -> list[PriceObservation]:
        """Return fresh price observations for known products."""
