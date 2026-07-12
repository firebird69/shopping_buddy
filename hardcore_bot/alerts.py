from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable, Sequence

from .models import AlertCandidate, PriceObservation, WatchRule


def percent_drop(previous: float, current: float) -> float:
    if previous <= 0:
        return 0.0
    return max(0.0, (previous - current) / previous * 100.0)


def best_available_today(observations: Sequence[PriceObservation], now: datetime) -> dict[str, PriceObservation]:
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    winners: dict[str, PriceObservation] = {}
    for obs in observations:
        if not obs.available or obs.observed_at < start or obs.observed_at > now:
            continue
        current = winners.get(obs.product_id)
        if current is None or obs.price_uah < current.price_uah:
            winners[obs.product_id] = obs
    return winners


def evaluate_watch_rule(
    rule: WatchRule,
    latest: PriceObservation,
    previous_price: float | None,
    today_best: PriceObservation | None,
    last_alert_at: datetime | None,
    now: datetime,
    lang: str = "uk",
) -> list[AlertCandidate]:
    if not latest.available:
        return []
    if last_alert_at and now - last_alert_at < timedelta(hours=rule.cooldown_hours):
        return []

    alerts: list[AlertCandidate] = []
    if previous_price is not None:
        drop = percent_drop(previous_price, latest.price_uah)
        if drop >= rule.drop_percent:
            alerts.append(AlertCandidate(rule.user_id, rule.product_id, latest.retailer, latest.price_uah, f"drop:{drop:.1f}", lang, latest.url))

    if rule.threshold_uah is not None and latest.price_uah <= rule.threshold_uah:
        alerts.append(AlertCandidate(rule.user_id, rule.product_id, latest.retailer, latest.price_uah, "threshold", lang, latest.url))

    if rule.best_today and today_best is not None and today_best.retailer == latest.retailer and today_best.price_uah == latest.price_uah:
        alerts.append(AlertCandidate(rule.user_id, rule.product_id, latest.retailer, latest.price_uah, "best_today", lang, latest.url))

    # De-duplicate same product/store/price reasons by priority.
    if not alerts:
        return []
    priority = {"threshold": 0, "drop": 1, "best_today": 2}
    alerts.sort(key=lambda a: priority.get(a.reason.split(":", 1)[0], 9))
    return [alerts[0]]


def reason_kind(reason: str) -> str:
    return reason.split(":", 1)[0]
