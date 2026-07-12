# The Hardcore Bot — Next Week Work Plan

**Planning window:** 2026-07-12 to 2026-07-18 Kyiv time
**Prepared:** 2026-07-11 22:37 Kyiv / 19:37 UTC
**Current phase:** Source-backed MVP hardening with user-selected Product/SKU watchlists

## Goal for the Week

Move from a demo-only Telegram MVP plus source feasibility spike to a source-backed alpha where a user can browse/select Product/SKU choices, add them to a personal watchlist, and receive best-price or meaningful-drop alerts from safe low-volume public sources.

## Current Advancement Summary

- Core Python package exists with SQLite schema, product/watchlist/observation storage, alert rule evaluation, bilingual formatting, CLI commands, and optional aiogram Telegram entrypoint.
- Demo collector can seed deterministic observations and prove digest behavior without external dependencies.
- Tests cover alert percentage/cooldown behavior plus SQLite roundtrip and bilingual digest formatting.
- Source feasibility is stronger than originally assumed: two low-volume spike passes succeeded for ATB, official Auchan GraphQL, Zakaz-Novus `__NEXT_DATA__`, Fora public catalog API replay, and THRASH GraphQL offers.
- The key remaining risk is not “can we fetch anything?” but “can we map selectable SKUs consistently, preserve store/filial context, and avoid misleading users about live shelf-price accuracy?”
- Product direction clarified on 2026-07-11: the system should not only push a curated basket; the core flow is “I pick the product, it notifies me of the best price.”
- Initial catalog clarified on 2026-07-11: first products are Pepsi Black 2L, AHA fruit/honey muesli 330g, President sour cream 15% 300g, and Yagotynske UHT milk 2.6% 900g, seeded from ATB URLs.
- Source priority clarified on 2026-07-11: ATB, Fora, and THRASH are primary; Auchan and Novus are secondary/nearby.
- Alert policy clarified on 2026-07-12: strict exact SKU only, one daily contact around 09:00 Kyiv by default, Ukrainian default copy, minimal setup, no separate price-query command for MVP, and no inclusion of non-identical products.

## Success Criteria by End of Week

1. A user can select Product/SKU watches with minimal setup and default alert settings.
2. A real-source collector path exists for at least 2 first-tier sources and normalizes into the existing `PriceObservation`/SQLite flow or a documented extension of it.
3. A selectable SKU mapping file exists for 10–20 grocery items with source-specific product IDs/queries and confidence notes.
4. CLI/Telegram can run a safe collection pass against selected real sources and produce a user-specific daily digest with all covered-store prices from the DB.
5. Telegram demo path is smoke-tested locally with no token requirement for core logic and clear operator instructions for live token mode.
6. Source caveats are explicit in UX/docs: online-source deal discovery, not guaranteed live in-store shelf prices.

## Day-by-Day Plan

### Day 1 — Stabilize Baseline, User Flow, and Data Model

- Run full tests in a clean `.venv` and record current evidence in `STATUS.md`.
- Confirm user flow: minimum setup → selected Product/SKU watchlist → optional digest time/threshold/drop settings → once-daily 09:00 Kyiv digest with all covered-store prices.
- Decide whether `PriceObservation` needs fields beyond current `product_id`, `retailer`, `price_uah`, `observed_at`, `available`, `url` before real collectors land.
- Likely additions to consider: `source`, `store_or_filial`, `source_product_id`, `old_price_uah`, `discount_until`, `raw_json` or separate source observation table.
- Decide whether `WatchRule` needs user-facing preferences beyond current `drop_percent`, `threshold_uah`, `best_today`, and `cooldown_hours`.
- Add tests for any schema/model migration before changing implementation.

### Day 2 — Selectable SKU Catalog and Mapping

- Create `data/source_mappings/` with a reviewed mapping format for 10–20 MVP SKUs.
- Start with the four user-selected ATB products already in `data/seed_products.json`, then expand only if source evidence is available.
- For each item, record source-specific identifiers/query terms, size/unit assumptions, and confidence.
- Add validation script/test that rejects missing product IDs, duplicate mappings, or unsupported source names.
- Add internal list/filter/search helpers so setup does not depend on memorizing product IDs, but do not expose a separate manual price-query command in MVP.

### Day 3 — First Real Collector: ATB or Fora

- Promote one clean public structured source from spike to a production-style collector under `hardcore_bot/collectors/`.
- Prefer ATB first if product-page parsing is stable enough for the user-selected URLs; otherwise use Fora API first because it returned structured product data without browser automation.
- Keep request volume tiny, timeout explicit, and source-specific errors non-fatal.
- Add unit tests using fixture responses; do not make tests depend on live network.

### Day 4 — Second Real Collector: Fora or THRASH

- Add one contrasting priority source: Fora if ATB was first, or THRASH if ATB/Fora are already covered enough for comparison.
- Keep Auchan and Novus nearby as fallback/comparison sources, not the first implementation priority unless ATB/Fora/THRASH mapping fails for the selected products.
- Make parser tolerant and fixture-backed.
- Persist enough context to explain price provenance in digests/alerts.
- Update `docs/source-feasibility.md` if implementation findings change earlier assumptions.

### Day 5 — CLI Integration and Alert Pipeline

- Add CLI command(s) for real collection, for example `collect-source --source auchan --limit 20` or `collect-real --sources auchan,fora`.
- Ensure collection writes observations to SQLite and can be followed by `digest` without manual transformation.
- Wire alert evaluation over per-user watchlists; avoid alerts for products the user did not choose.
- Add only the minimum user-facing setup needed for watchlist management and optional digest time/threshold/drop percent; daily digest is the primary product surface.
- Add tests for CLI paths with fake collectors or fixtures.

### Day 6 — Operator Demo and Telegram Readiness

- Run a local end-to-end demo: init DB, seed, collect from fixture or live low-volume source, digest, watchlist/alert evaluation.
- Review Telegram command behavior and language handling; fix hard-coded Ukrainian output in commands that should respect user language.
- Write concise operator notes in README for alpha operation, source cadence, and caveats.

### Day 7 — Review, Polish, and Go/No-Go

- Re-run tests and a low-volume live source smoke test if allowed.
- Compare collected prices across passes for stability and obvious mapping mistakes.
- Decide go/no-go for a private alpha Telegram bot with limited users.
- Update `STATUS.md` with final week outcome and next unblocked action.

## Recommended Priority Order

1. User-selectable catalog/watchlist flow.
2. Schema/model decision for real source metadata and watch preferences.
3. Mapping file and validator.
4. One structured collector with fixture tests.
5. CLI/Telegram integration for user-specific alerts.
6. Second source.
7. Telegram language/copy polish.
8. Deployment/operator docs.

## Risks and Pushback

- **Accuracy risk:** Zakaz and similar sources can be fulfillment/store specific. Store/filial context must be persisted; copy must not imply guaranteed shelf-price truth. Sandbox assumption is Kyiv network pricing, but evidence should still record store/filial or delivery context where available.
- **Matching risk:** MVP is strict exact SKU only. Do not include non-identical pack sizes, variants, flavors, or near substitutes in the daily digest.
- **Maintenance risk:** HTML parsers such as ATB are more brittle than GraphQL/API sources, but ATB is now product-priority source #1 because the initial catalog is ATB-seeded. Do it with fixture tests and graceful degradation.
- **Scope risk:** Adding many retailers before mappings and alerts are solid will create demo noise. Two reliable sources beat five fragile ones.
- **Legal/operational risk:** Keep low-frequency public access only; no login, private API interception, proxies, or bypass techniques.

## Validation Plan

- Unit: `python -m pytest -q`
- Docs hygiene: `git diff --check`
- Source smoke, when intentionally run: `python scripts/source_spike.py --label <label>` or a future real collector CLI with low limits.
- End-to-end demo: init DB, seed, collect, digest, and alert evaluation against a temporary SQLite DB.
