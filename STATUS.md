# The Hardcore Bot — Status

**Last updated:** 2026-07-12 23:32 Kyiv / 2026-07-12 20:32 UTC
**Current phase:** Initial MVP baseline is committed locally on `main`; GitHub remote is configured, but push is blocked by read-only SSH key permissions.

## What We're Building

The Hardcore Bot is a Telegram-native Kyiv grocery price alert MVP. Users should be able to select Product/SKU choices themselves, then receive alerts when those watched products hit a meaningful percentage drop, threshold, or best observed price.

The MVP deliberately avoids broad scraping promises. The intended alpha is low-volume public-source deal discovery for a small Kyiv basket, with clear caveats that online platform prices are not guaranteed live in-store shelf prices.

## Current State

### ✅ What's Done

- [x] Python package scaffold exists under `hardcore_bot/` with models, SQLite storage, alert rules, bilingual formatting, CLI, and optional aiogram Telegram entrypoint.
- [x] SQLite schema covers users, products, price observations, watchlists, and sent alerts.
- [x] Demo collector produces deterministic observations so the core app can be tested without scraping or a Telegram token.
- [x] Initial user-selected catalog exists in `data/seed_products.json` with four ATB-seeded products: Pepsi Black 2L, AHA fruit/honey muesli 330g, President sour cream 15% 300g, and Yagotynske UHT milk 2.6% 900g.
- [x] Initial source mapping file exists at `data/source_mappings/initial_catalog.json` with user-provided ATB URLs.
- [x] Alert policy confirmed: strict exact SKU only; one daily digest at 09:00 Kyiv by default; Ukrainian default copy; no product-price query command for MVP; include all covered-store prices in the daily contact; urgent conditions are threshold hit or 15%+ drop but still constrained to the daily contact model unless explicitly changed.
- [x] Tests cover alert drop/cooldown behavior and storage/formatting roundtrip.
- [x] Source feasibility notes exist in `docs/source-feasibility.md`, including the 2026-07-11 target-event verdict.
- [x] Low-volume source spike passes succeeded for ATB, official Auchan GraphQL, Zakaz-Novus, Fora API replay, and THRASH GraphQL offers. Evidence lives in `data/source_spikes/`.
- [x] `scripts/source_spike.py` supports target-date/range checks and JSON channel config for adding/reparameterizing channels that reuse existing source kinds.
- [x] Repo pickup docs now exist: `AGENTS.md`, `STATUS.md`, and `docs/next-week-work-plan.md`.
- [x] Repo git strategy source of truth exists at `docs/git-strategy.md`, including explicit staging, commit naming, no-push default, validation, and closeout routine.
- [x] Price observations now support real-source provenance: `source`, `source_product_id`, `store_or_filial`, `old_price_uah`, `discount_until`, and `raw_json`, with backward-compatible SQLite migration.
- [x] Initial source mapping validation exists in `hardcore_bot/source_mappings.py` and validates allowed sources, unique product IDs, seed-product references, confidence, and URL/source identifier/query presence.
- [x] Daily digest data foundation exists in `hardcore_bot/digest.py`: latest prices are grouped per product, available prices sort cheapest/best first, unavailable/missing covered stores are represented, and watched SKUs can appear before first observation.
- [x] **New:** ATB collector foundation in `hardcore_bot/collectors/atb.py`: `parse_atb_product_page()` extracts price, availability, old_price, discount_until, product ID, store/filial, title, and raw data attributes from ATB product-page HTML using regex (no new dependencies). `AtbCollector` class implements the `Collector` ABC, integrates with existing source mappings via normalized product-id-to-ATB-URL lookup, and gracefully handles fetch errors as unavailable observations.
- [x] **New:** Four realistic ATB product-page fixture HTML files under `tests/fixtures/atb/` covering: normal in-stock, in-stock with title/brand, out-of-stock (disabled add-to-cart), and promo product (old price + discount until).
- [x] **New:** Nine fixture-backed tests in `tests/test_atb_collector.py` covering: price/provenance extraction, title/brand, unavailable detection, promo parsing (old_price_uah + discount_until), invalid HTML resilience, URL-to-product-id mapping, product-id-to-URL collector lookup, query-param stripping in mapping URLs, and full `AtbCollector.collect()` integration with a mock session.

### 🔄 What's In Progress

- [ ] Mapping the initial four selected products across priority sources after ATB: Fora and THRASH first, with Auchan and Novus nearby.
- [ ] Adding CLI/Telegram integration for safe low-volume real collection using the ATB collector.

### ⏳ What's Next

1. Promote user-selected Product/SKU watchlists to the center of the MVP: catalog browse/search, add/remove watch, list my watches, and threshold preferences.
2. Keep setup minimal: default subscriptions/settings are enough for private alpha; only expose adjustable digest time and optional thresholds/drop percent if needed.
3. Add ATB collector CLI integration — a `collect atb` command that reads fixtures or does live low-volume fetches, writes observations to SQLite.
4. Add Fora/THRASH mappings for the same selected SKUs where available; do not include non-identical substitutions.
5. Add a second priority source, preferably Fora or THRASH after ATB, with Auchan/Novus as fallback/comparison sources.
6. Smoke-test an end-to-end user flow and update README/operator notes.

### 🚫 Blocked / Constraints

- Live Telegram mode requires `TELEGRAM_BOT_TOKEN`; core CLI/tests should remain token-free.
- Real collectors must stay low-volume and public-source only: no login, private API interception, WAF bypass, proxies, or high-frequency scraping.
- Price copy must be careful: source data is useful for online deal discovery and directional price intelligence, not guaranteed shelf-price truth.
- Initial git baseline is committed. Continue using explicit staging only; do not use broad `git add .`.
- GitHub push to `git@github.com:firebird69/shopping_buddy.git` is blocked in this environment: `ERROR: The key you are authenticating with has been marked as read only.` Operator needs a write-capable deploy key/account key, HTTPS token push, or to push from a machine with write access.
- Local environment note: `python3 -m venv .venv` is blocked because `ensurepip` / `python3.10-venv` is missing on this host. Baseline tests were run with user-installed `pytest` via `python3 -m pytest -q`.

## Latest Advancement Review

The ATB collector foundation is the first real-source production-style collector. It was built by inspecting the live ATB product-page HTML structure (price format, data attributes, title, availability class, promo labels), then creating representative fixtures that lock parser behavior without claiming live truth. The parser/debug loop used `parse_atb_product_page()` directly on fixture content without live HTTP in tests.

The collector:
- Uses only stdlib + `requests` (already a dependency); no new packages
- Implements the existing `Collector` ABC
- Integrates with existing source mappings via normalized `mapping_product_id_to_url()` for collection, with `mapping_url_to_product_id()` retained for reverse lookup/tests
- Parses price, product ID (data-productid), store/filial, old_price, discount_until, title, and raw data-* attributes
- Detects availability via `b-addToCart--disabled` CSS class
- Handles promo products (old_price + discount_until), invalid HTML, and fetch errors gracefully
- Has 9 fixture-backed tests; review fixed a lookup-shape issue where the collector originally built URL-to-product lookup but used it as product-to-URL, relying on a fallback scan

Validation: 47/47 pytest pass in 0.47s, JSON syntax for seed and mapping files, mapping validator returns 0 errors (`mapping validation passed`), `git diff --check` clean.

## Next Week Plan

See `docs/next-week-work-plan.md` for the detailed 2026-07-12 to 2026-07-18 plan. Summary priorities:

1. User-selectable Product/SKU catalog and watchlist UX.
2. Schema decision for both source provenance and user-specific watch preferences.
3. Selectable SKU source mapping.
4. First fixture-tested structured collector.
5. CLI/Telegram integration for real collection and user-specific alerts.
6. Second source and end-to-end user demo.
7. README/operator caveats and go/no-go for private alpha.

## Key Files

| File | Purpose |
|---|---|
| `AGENTS.md` | Agent policies and repo operating constraints |
| `STATUS.md` | Living pickup state; read first, update after meaningful work |
| `README.md` | Product overview, quick start, Telegram commands |
| `docs/git-strategy.md` | Git source of truth: branch model, explicit staging, commit naming, validation, no-push default, and closeout routine |
| `docs/next-week-work-plan.md` | Detailed work plan for the next week |
| `docs/source-feasibility.md` | Source feasibility findings, source priority decisions, and target-event verdict |
| `docs/source-channels.example.json` | Example external channel config for `scripts/source_spike.py` |
| `scripts/source_spike.py` | Low-volume public-source spike runner |
| `data/source_spikes/` | JSON/Markdown source spike evidence |
| `data/seed_products.json` | Current seed product basket |
| `hardcore_bot/storage.py` | SQLite schema and persistence helpers |
| `hardcore_bot/alerts.py` | Alert rule evaluation |
| `hardcore_bot/collectors/` | Collector interface and demo collector |
| `hardcore_bot/cli.py` | Local CLI commands |
| `hardcore_bot/bot.py` | Optional aiogram Telegram bot entrypoint |
| `tests/` | Unit tests |

## How to Pick Up Work

1. Read `AGENTS.md` and this file.
2. Check `docs/git-strategy.md` for the repo git routine before staging/committing.
3. Check `git status --short --branch`.
4. Run baseline validation with `python3 -m pytest -q`. If you want an isolated environment first, install `python3.10-venv` or use another environment manager; this host currently lacks `ensurepip` for stdlib `venv`.
5. Open `docs/next-week-work-plan.md` and start with Day 1 / priority 1 unless the user redirects.
6. Update this file after completing a meaningful step.

## Environment

- Workspace: `/workspace/projects/the-hardcore-bot`
- Branch: `main`
- Git remote: `origin` -> `git@github.com:firebird69/shopping_buddy.git`
- Git state at this update: initial baseline committed locally at `74305d3`; working tree expected clean; upstream tracking not established because push failed with read-only SSH key.
- Python requirement: `>=3.10`
- Main test command after dev install: `python -m pytest -q`
- Latest validation: `python3 -m pytest -q` passed, 47 tests, on 2026-07-12 20:05 UTC; `python3 -m json.tool` passed for `data/seed_products.json` and `data/source_mappings/initial_catalog.json`; `check_mappings('data/source_mappings/initial_catalog.json', 'data/seed_products.json')` passed; `git diff --check` passed.
- Demo DB path: `data/hardcore.sqlite3` (ignored)
- Secrets policy: no `.env`, tokens, cookies, or session files in repo.

## Recent Activity

- 2026-07-12 23:32 Kyiv — Configured GitHub remote `origin` and renamed local branch to `main`; attempted `git push -u origin main`, but GitHub rejected the SSH key as read-only. Local commit remains `74305d3` and working tree was clean before this status update.
- 2026-07-12 23:10 Kyiv — Created the initial git baseline commit after adding `docs/git-strategy.md` as the repo git source of truth, following the agreed convention: explicit staging only, concise conventional commit naming, no-push default, and task closeout evidence.
- 2026-07-12 22:43 Kyiv — Reviewed ATB collector slice, fixed collector mapping lookup to use product-id-to-normalized-URL directly, added regression coverage, and validated: 47 pytest tests, JSON syntax checks, real mapping validation, and `git diff --check`.
- 2026-07-12 00:27 Kyiv — Implemented first build slice: source provenance fields and SQLite migration, strict mapping validator, daily digest data helpers, and regression coverage for schema compatibility, mapping validation, best-price ordering, missing covered stores, and watched SKUs without observations. Validation passed: 38 pytest tests, JSON syntax checks, real mapping validation, and `git diff --check`.
- 2026-07-11 23:31 Kyiv — User selected the first four products via ATB URLs; updated `data/seed_products.json`, added `data/source_mappings/initial_catalog.json`, and set source priority to ATB/Fora/THRASH first with Auchan/Novus nearby.
- 2026-07-12 00:11 Kyiv — Alert/product policy confirmed: strict exact SKU only, no non-identical substitutions, one daily 09:00 Kyiv digest by default, Ukrainian default, minimal setup, all covered-store prices included in the daily contact rather than a separate price query command.
- 2026-07-11 23:10 Kyiv — Product direction clarified: users must be able to select Product/SKU choices themselves; next-week plan pivots from purely curated basket hardening to selectable catalog + watchlist + user-specific alerts.
- 2026-07-11 22:45 Kyiv — Upgraded `scripts/source_spike.py` with target-date/range assessment and JSON channel config; added source-spike tests and `docs/source-channels.example.json`; validated July 1–2 plus July 12 target coverage with 5/5 live channels and 25 normalized items; verdict: good enough for target-event evidence, not yet production real-source alerting.
- 2026-07-11 22:38 Kyiv — Reviewed current repo state, source spike evidence, and MVP code; created pickup docs and next-week work plan; `python3 -m pytest -q` passed (6 tests).
- 2026-06-26 UTC — Source spike pass 2 succeeded for all five core sources with 5 normalized items each.
- 2026-06-26 UTC — Source spike pass 1 fixed succeeded for all five core sources and justified real-source MVP work.
