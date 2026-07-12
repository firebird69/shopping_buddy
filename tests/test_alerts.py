from datetime import datetime, timedelta

from hardcore_bot.alerts import best_available_today, evaluate_watch_rule, percent_drop
from hardcore_bot.models import PriceObservation, WatchRule


def test_percent_drop_returns_percentage_decrease():
    assert percent_drop(100, 85) == 15


def test_best_available_today_ignores_out_of_stock_and_old_observations():
    now = datetime(2026, 6, 24, 12, 0)
    observations = [
        PriceObservation("pepsi-2l", "A", 50, now - timedelta(days=1), True),
        PriceObservation("pepsi-2l", "B", 45, now, False),
        PriceObservation("pepsi-2l", "C", 48, now, True),
    ]
    winners = best_available_today(observations, now)
    assert winners["pepsi-2l"].retailer == "C"


def test_evaluate_watch_rule_emits_drop_alert_when_price_falls_enough():
    now = datetime(2026, 6, 24, 12, 0)
    rule = WatchRule(user_id=123, product_id="pepsi-2l", drop_percent=10, best_today=False)
    latest = PriceObservation("pepsi-2l", "A", 80, now, True)
    alerts = evaluate_watch_rule(rule, latest, previous_price=100, today_best=None, last_alert_at=None, now=now)
    assert len(alerts) == 1
    assert alerts[0].reason.startswith("drop:")


def test_evaluate_watch_rule_respects_cooldown():
    now = datetime(2026, 6, 24, 12, 0)
    rule = WatchRule(user_id=123, product_id="pepsi-2l", drop_percent=10, best_today=False, cooldown_hours=24)
    latest = PriceObservation("pepsi-2l", "A", 70, now, True)
    alerts = evaluate_watch_rule(rule, latest, previous_price=100, today_best=None, last_alert_at=now - timedelta(hours=2), now=now)
    assert alerts == []
