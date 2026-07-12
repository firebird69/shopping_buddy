from datetime import date

from scripts import source_spike


def test_parse_targets_supports_ranges_and_commas():
    assert source_spike.parse_targets(["2026-07-01..2026-07-02,2026-07-05"]) == [
        date(2026, 7, 1),
        date(2026, 7, 2),
        date(2026, 7, 5),
    ]


def test_discount_until_parses_iso_dotted_and_fetched_year():
    fetched_at = "2026-07-11T12:00:00+00:00"
    assert source_spike.parse_discount_until("2026-07-22", fetched_at) == date(2026, 7, 22)
    assert source_spike.parse_discount_until("19.07.2026", fetched_at) == date(2026, 7, 19)
    assert source_spike.parse_discount_until("14.07", fetched_at) == date(2026, 7, 14)


def test_event_assessment_counts_active_and_unknown_promos():
    fetched_at = "2026-07-01T12:00:00+00:00"
    items = [
        source_spike.SpikeItem("a", "A", None, "1", None, None, "active", 10, 15, None, "2026-07-02", True, None, None, fetched_at, {}),
        source_spike.SpikeItem("b", "B", None, "2", None, None, "unknown", 10, 15, None, None, True, None, None, fetched_at, {}),
        source_spike.SpikeItem("c", "C", None, "3", None, None, "expired", 10, 15, None, "2026-06-30", True, None, None, fetched_at, {}),
    ]
    ass = source_spike.assess_events(items, [date(2026, 7, 1)])["2026-07-01"]
    assert ass.active_promos == 1
    assert ass.unknown_dated_promos == 1
    assert ass.expired_or_not_covering == 1


def test_channel_selection_allows_configured_channels():
    channels = [source_spike.Channel("x", "auchan_graphql_search", "X")]
    assert source_spike.selected_channels(channels, "x") == channels
