# Source feasibility notes — preliminary

The MVP should not start with full grocery catalog scraping. The safest collector path is:

1. Manual product mapping for 10–20 SKUs.
2. Low-frequency fetches, 2–4/day.
3. Prefer public structured endpoints discovered from public pages.
4. Use Playwright only for source inspection or hard dynamic pages, not bulk scraping.
5. Avoid login, private mobile API interception, WAF bypass, and proxies for MVP.

Initial source priority:

| Source | MVP role | Notes |
|---|---|---|
| Zakaz.ua ecosystem | High-value catalog candidate | Inspect public pages/network for structured JSON; prices may be zone/store dependent. |
| Fora | High-value retailer API candidate | Definitely worth adding: public web app calls catalog APIs that return product prices/promotions. |
| THRASH!ТРАШ! | High-value promo/deal candidate | Definitely worth adding: public GraphQL returns active promo/product offer data. |
| GoToShop/promos | Deal/flyer candidate | Better for sale detection than exact live stock. |
| ATB | Must-have retailer | Include in the pre-MVP source spike. Public pages return product-card data with IDs, discount/category/brand/currency attributes and visible prices; treat as low-rate HTML parsing unless a cleaner endpoint is found. |
| Novus | First-tier via Zakaz | `novus.zakaz.ua` is already proven through `__NEXT_DATA__`; include in pre-MVP spike. |
| Varus | Pre-MVP reconnaissance candidate | Public page exposes API/GraphQL/product/price signals. Include a small endpoint-discovery pass, but do not block MVP on it. |
| Silpo | Pre-MVP reconnaissance only | Public HTML contains product/category/price data, but Playwright hit Cloudflare; include only as a bounded probe, not as a required source. |
| Auchan official `auchan.ua` | Best final-chain candidate | Official site is directly fetchable, no Cloudflare in curl, and exposes a public Magento-style `/graphql` endpoint returning product/search price data. Prefer this over Zakaz where possible. |
| Auchan via Zakaz | Fallback/comparison source | `auchan.zakaz.ua` is directly fetchable and exposes structured `__NEXT_DATA__` promo/product data; useful as fallback and for comparing official-vs-Zakaz price behavior. |
| Metro via Zakaz | Optional comparator | Same Zakaz retailer-subdomain pattern; useful later if we need wholesale/bulk comparison, but not necessary for pre-MVP. |

Go/no-go for real collectors: at least 2–3 sources should provide stable public product/promotional prices for curated SKUs without high request volume or security bypass.

## Target-event verdict — 2026-07-11

The current `scripts/source_spike.py` is **good enough** for the requested target-event evidence task. It is not impossible, and it is no longer only a hand-written one-off: it has a small channel registry, JSON channel config support, target-date parsing, and event coverage reporting.

Latest run:

- Command: `python3 scripts/source_spike.py --label final_july_target_check --target-date 2026-07-01..2026-07-02 --target-date 2026-07-12`
- JSON: `data/source_spikes/source_spike_final_july_target_check_20260711T194403Z.json`
- Report: `data/source_spikes/source_spike_final_july_target_check_20260711T194403Z.md`
- Result: 5/5 channels returned live items, 25 normalized items total.
- Target coverage: 16 active dated promos and 2 unknown-dated discounts for each checked target date: 2026-07-01, 2026-07-02, and 2026-07-12.

Channel flexibility was also tested with a one-channel external config:

- Command: `python3 scripts/source_spike.py --label final_config_example_check --channel-config docs/source-channels.example.json --target-date 2026-07-12`
- JSON/report output was created in `data/source_spikes/`.
- Result: configured `custom_auchan_coffee` channel returned 2 live items from the existing `auchan_graphql_search` kind.

Interpretation:

- **Good enough:** low-volume event/date validation, promo evidence gathering, and adding channels that reuse existing source kinds.
- **Not good enough yet:** production alerting from real retailer data, long-term monitoring, or claims of exact in-store shelf-price truth. The next step for that is promoting 1–2 source kinds into fixture-tested collectors that write provenance-rich observations into SQLite.

Current supported channel kinds: `atb_homepage`, `auchan_graphql_search`, `fora_catalog_search`, `thrash_offers`, and `zakaz_next_data`.

## Actual inspection — 2026-06-25

Quick live checks show there is enough source value to validate collectors before building more MVP surface area.

### Source spike pass 1 — 2026-06-26

First normalized low-volume fetch pass succeeded for all five core sources. Artifact paths:

- JSON: `data/source_spikes/source_spike_pass1_fixed_20260626T005818Z.json`
- Report: `data/source_spikes/source_spike_pass1_fixed_20260626T005818Z.md`

| Source | Result | Items | Notes |
|---|---:|---:|---|
| ATB homepage HTML | OK | 5 | Discount product cards parsed with product IDs, shop IDs, category/brand/currency attrs, current/old prices, promo end text. |
| Official Auchan GraphQL | OK | 5 | Public `https://auchan.ua/graphql` product search returned SKU/title/stock/regular/final price. |
| Zakaz-Novus `__NEXT_DATA__` | OK | 5 | Homepage promotion/product payload normalized from embedded Next.js data. |
| Fora API replay | OK | 5 | Public replay of `GetSimpleCatalogItems` returned product and promo price fields without persisted browser JWT/cookies in this pass. |
| THRASH GraphQL | OK | 5 | Public `offersSplited` query returned active promo products after updating field selection from stale `lagerId` to current `articul`. |

This is enough to justify building the MVP around real source constraints, pending a second pass to check short-term stability.

| Source | Result | Evidence | MVP implication |
|---|---|---|---|
| Zakaz retailer subdomains: `novus.zakaz.ua`, `auchan.zakaz.ua`, `metro.zakaz.ua` | Promising | Public HTML contains `__NEXT_DATA__` with product records: `ean`, `sku`, `title`, integer `price`, `discount.old_price`, `discount.due_date`, `currency`, `unit`, `in_stock`, images, and similar products. Product pages are directly fetchable without login in low-volume tests. `auchan.zakaz.ua/en/` returned status 200 with 31 product links and promo samples such as cucumber/tomato/mince with current price, old price, and due date. | Best first collector candidate for Zakaz-backed retailers. Use Zakaz-Novus immediately; use Zakaz-Auchan mainly as fallback/comparison now that official `auchan.ua` GraphQL is available. Prices appear to be minor units: e.g. `7999` = 79.99 UAH. Validate city/store dependence before relying on comparisons. |
| Fora `fora.ua` | Very promising | The SPA uses public JSON endpoints including `https://api.catalog.ecom.fora.ua/api/2.0/exec/EcomCatalogGlobal`. A direct low-volume POST to `GetSimpleCatalogItems` with `customFilter: "молоко"`, `filialId: 310`, `merchantId: 2`, `deliveryType: 2` returned products with `id`, `name`, `unit`, `price`, `oldPrice`, `promotion.startFrom`, `promotion.stopAfter`, `slug`, image, and category data. `GetCategories` and `GetPromotionCollection` also returned structured JSON. | Add as first-tier source spike beside Zakaz. It is better than generic scraping because product data comes from the web app's catalog API. Must validate filial/store selection and whether `deliveryType` changes price/availability. |
| THRASH!ТРАШ! `thrash.ua` | Very promising for promos/deals | The public web app uses `https://thrash.ua/graphql`. Captured `offers` GraphQL query returned `offersSplited.products.count = 777` with product fields including `id`, `slug`, `lagerId`, `title`, `weight`, `available`, `price`, `oldPrice`, `discountPercent`, `promotion`, and `activePeriod`; also returned promo cards. | Add as first-tier promo/deal source. It may be less like a full grocery catalog and more like active offers, which is useful for the bot if framed as deals/promos rather than exact full-basket price coverage. Validate whether `filialIds`/nearest store filtering changes the result. |
| Auchan official `auchan.ua` | Very promising | `https://auchan.ua/` returned status 200, no Cloudflare challenge, Next.js chunks, and GraphQL/API signals. Direct POST to `https://auchan.ua/graphql` worked without login. `storeConfig` returned `base_currency_code: UAH`; `products(search: "молоко", pageSize: 3)` returned `total_count: 156` and item fields including `sku`, `name`, `url_key`, `stock_status`, `regular_price`, `final_price`, `discount`, and currency. | Prefer official Auchan over Zakaz-Auchan for the main collector if product/category queries remain stable. Keep Zakaz-Auchan as a fallback and a validation comparator because Zakaz prices can differ by fulfillment store/platform terms. |
| `zakaz.ua/en/` root | Not useful directly | Root returned Cloudflare challenge in curl and Playwright. | Do not scrape the root; use retailer subdomains/product pages only. |
| ATB `atbmarket.com` | Must-have but slightly more brittle | Public pages return product cards and embedded add-to-cart attributes: `data-productid`, `data-shopid`, `data-itemid`, `data-brand`, `data-category`, `data-discount`, `data-currency`, plus visible price text. A direct low-volume fetch of `https://www.atbmarket.com/` returned status 200 and discount product-card data; generic/Catalog paths may show Cloudflare markers or errors, so keep request volume low and parser tolerant. | Include in the core pre-MVP spike. ATB has enough coverage/market importance that the MVP should try to support it even if the first collector is HTML-based rather than a clean API. Validate 5 curated product/category URLs twice before building UX promises around it. |
| GoToShop `gotoshop.ua` | Weak for direct collection from this runtime | Root returned Cloudflare challenge in curl and Playwright. | Defer unless there are RSS/static flyer endpoints or a permissive path discovered later. |
| Varus `varus.ua` | Worth a bounded pre-MVP probe | Public home page is accessible and exposes GraphQL/API/product/price signals. It is probably not harder than Fora/THRASH at the discovery stage, but needs network/request capture and endpoint replay before we know if it is collector-friendly. | Include in pre-MVP investigation as a 30–60 minute endpoint-discovery task. Do not make it a required MVP source unless a clean public catalog/product endpoint is replayable without login/bypass. |
| Silpo `silpo.ua` | High-value but higher-risk | Direct HTML fetch returned a large public page with category/product/price signals and visible category/product links. Playwright navigation hit a Cloudflare challenge, so browser-driven discovery is less reliable from this runtime. | Include only as a bounded pre-MVP reconnaissance task. If curl/HTML parsing or public static payloads are enough, keep it; if it requires browser challenge handling, defer. |

### Pre-MVP scope decision for Novus / Varus / Silpo

- **Novus: include.** It is not too hard because `novus.zakaz.ua` follows the proven Zakaz retailer-subdomain pattern with structured `__NEXT_DATA__` product payloads.
- **Varus: include as investigation, not as a promised source.** The public site exposes GraphQL/API/product/price signals, so it is worth checking before MVP assumptions harden. Timebox endpoint discovery and replay.
- **Silpo: include as reconnaissance only.** It is commercially important and has product/price data in public HTML, but Cloudflare appeared in Playwright. Keep it in the pre-MVP investigation only if a low-friction curl/static/endpoint route is found; otherwise defer without treating that as a blocker.

### Final extra-chain candidate: Auchan

If we need one final candidate beyond the already-promising Fora/THRASH/Zakaz-Novus path, **official Auchan (`auchan.ua`) is now the strongest choice**. It gives us the real retailer source instead of a Zakaz intermediary and exposes a directly replayable public GraphQL endpoint. `auchan.zakaz.ua` remains useful as fallback/comparison, but should not be the preferred Auchan source if the official endpoint remains stable.

Recommended pre-MVP basket:

1. ATB product/card samples.
2. Official Auchan GraphQL product/search samples.
3. Zakaz-Novus product/promo samples.
4. Fora API product/promo samples.
5. THRASH GraphQL promo samples.
6. Optional: Zakaz-Auchan samples for official-vs-Zakaz comparison.

Keep Varus and Silpo as later expansion/recon sources unless the above basket fails.

## Zakaz promotion/price accuracy research

What can be concluded from public evidence:

1. **Zakaz prices are operationally tied to the store that fulfills the order, not a universal shelf-price truth.** The public offer text says goods are sold at prices set by the seller at the date/time of goods release in the relevant store from which the order is fulfilled.
2. **Platform prices can change before checkout fulfillment.** The same offer says prices shown on the platform at order time can be changed unilaterally by the seller according to prices at the moment of goods release in the relevant store.
3. **The fiscal receipt is the final source of truth.** The offer says the total cost is in the payment/fiscal document given with the goods, and the sum may vary depending on price, quantity, or assortment available in the corresponding store at release time.
4. **There is a tolerance/approval point for price changes.** If an ordered item's price changes by more than 5 UAH, the change must be agreed with the buyer or the seller can withdraw from that item sale.
5. **Promotions are not automatically the same as all offline shelf promotions.** Only discounts/promotions/special offers directly specified on the Platform are valid for Platform orders, and only if effective at the moment of goods release from the seller's store.
6. **No public statistical audit found in this quick pass.** I did not find a reliable public dataset saying “Zakaz promo prices match in-store prices X% of the time.” Treat any exact match-rate as unknown until we run our own receipt/shelf comparison.

Practical interpretation for this bot:

- Zakaz promo data is good enough for **online-order deal discovery** and likely useful for **directional price intelligence**.
- It is not safe to market it as guaranteed “live in-store shelf price” without store-level validation.
- Store/city/fulfillment matters. A collector should persist `retailer`, `chain`, selected city/store/filial if visible, delivery service, `fetched_at`, promo validity dates, and source URL.
- For accuracy validation, run a small audit: choose 20 promoted SKUs across Novus/Auchan/Metro, record Zakaz price/promo, then compare against either a completed order receipt or manual shelf/photo evidence from the same store/city. Repeat across at least two dates because promos expire and prices can change at goods release.

Recommended next move before more MVP work: build a tiny source spike, not the full collector. Fetch 5 curated Zakaz product URLs, 5 Fora API search/category entries, 5 THRASH GraphQL offer entries, and 5 ATB catalog/product entries; normalize to `{source, retailer, store_or_filial, sku/ean/lager_id, title, price_uah, old_price_uah, discount_until, promotion_id, in_stock_or_available, fetched_at, source_url}`; and run it twice a few hours apart. If values are stable and legally/operationally acceptable at 2–4 fetches/day, then proceed with the MVP around real source data instead of mock assumptions.
