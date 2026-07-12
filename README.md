# The Hardcore Bot — Kyiv Grocery Price Alert MVP

Telegram-native MVP for tracking curated grocery SKUs in Kyiv and alerting users when prices drop meaningfully or become the best observed price today.

## Current MVP scope

This repo is intentionally narrow:

- Bilingual Ukrainian/Russian message templates.
- SQLite storage for products, retailer offers, price observations, watchlists, and sent alerts.
- Alert rules for percentage drops, best-price-today, threshold, and cooldown suppression.
- Demo collector that produces deterministic observations so the app is testable without scraping or a Telegram token.
- Optional Telegram bot entrypoint using `aiogram` when `TELEGRAM_BOT_TOKEN` is provided.
- Source/channel spike script for low-volume public checks across ATB, Auchan, Zakaz-Novus, Fora, and THRASH.
- Source collectors are pluggable; production collectors should be promoted only after safe, low-volume source evidence.

## Why not full scraping yet?

The hard problem is reliable/legal/low-maintenance grocery data. The MVP therefore keeps scraping behind a collector interface and ships a demo collector plus source research notes. Real collectors should start with low-frequency public page/API checks for a small curated SKU set.

## Quick start

```bash
cd /home/ubuntu/projects/the-hardcore-bot
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
python -m pytest -q
python -m hardcore_bot.cli init-db --db data/hardcore.sqlite3
python -m hardcore_bot.cli seed --db data/hardcore.sqlite3
python -m hardcore_bot.cli collect-demo --db data/hardcore.sqlite3
python -m hardcore_bot.cli digest --db data/hardcore.sqlite3 --lang uk
```

## Source/channel spike verdict

The current source spike script is **good enough for target-event validation**, including the July 1–2 target window, as a pre-production evidence tool. It is not yet the production collector that writes real retailer observations into SQLite.

Latest validation on 2026-07-11 UTC:

```bash
python3 scripts/source_spike.py \
  --label july_target_check \
  --target-date 2026-07-01..2026-07-02 \
  --target-date 2026-07-12
```

Result: 5/5 live channels returned items, 25 normalized items total, and the report found dated active promos covering 2026-07-01, 2026-07-02, and 2026-07-12. Evidence files are written to `data/source_spikes/` as both JSON and Markdown.

To test adding or changing a channel without editing code, provide a config file:

```bash
python3 scripts/source_spike.py \
  --label config_flex_check \
  --channel-config docs/source-channels.example.json \
  --target-date 2026-07-12
```

Supported channel `kind` values now: `atb_homepage`, `auchan_graphql_search`, `fora_catalog_search`, `thrash_offers`, and `zakaz_next_data`. Adding another channel using one of those kinds is data-only; adding a brand-new protocol still needs one fetcher function plus a registry entry.

## Running Telegram bot

A token is not required for core tests or demo mode. For live Telegram:

```bash
export TELEGRAM_BOT_TOKEN="..."
python -m hardcore_bot.bot
```

Supported commands in MVP:

- `/start` — language and intro.
- `/lang_uk`, `/lang_ru` — language switch.
- `/products` — curated product list.
- `/watch <product_id>` — watch a product.
- `/digest` — current best prices.
- `/status` — health/status.

## Deployment notes

Use a systemd service or cron later. Do not schedule high-frequency scraping. Recommended initial cadence: 2–4 data collection runs/day.

## Safety posture

- No private app reverse-engineering.
- No login/cookies required for MVP collectors.
- No proxies initially.
- Respect robots/ToS and keep request volume low.
- Suppress unavailable/out-of-stock offers in alerts.
