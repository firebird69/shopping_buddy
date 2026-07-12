# Source/channel spike final_config_example_check — 2026-07-11T19:44:04.055913+00:00

## Verdict signal

- Live channels with items: **1/1**.
- Normalized items: **2**.
- Good-enough threshold for target-event monitoring: at least 3 live channels and at least one dated promo covering each target date, or an explicit operator decision to accept unknown-dated discounts.

## Channel summary

| Channel | Kind | Retailer | OK | Items | Evidence |
|---|---|---|---:|---:|---|
| custom_auchan_coffee | auchan_graphql_search | Auchan custom | yes | 2 | status=200; bytes=1682;  |

## Target event/date coverage

| Target date | Active dated promos | Unknown-dated discounts | Expired/not covering | Samples |
|---|---:|---:|---:|---|
| 2026-07-12 | 0 | 0 | 0 | - |

## Normalized items

- **Auchan custom** / `custom_auchan_coffee` / `719620` — Кава мелена Кава зі Львова Еспрессо, 450 г — 489.0 UAH
- **Auchan custom** / `custom_auchan_coffee` / `617054` — Кава мелена Кава зі Львова Вірменська, 225 г — 301.2 UAH

## Adding channels

Use `--channel-config channels.json`. Config shape:

```json
{
  "channels": [
    {
      "name": "auchan_official_milk",
      "kind": "auchan_graphql_search",
      "retailer": "Auchan",
      "enabled": true,
      "params": {
        "url": "https://auchan.ua/graphql",
        "search": "молоко",
        "store": "ua"
      }
    }
  ]
}
```

Supported `kind` values now: atb_homepage, auchan_graphql_search, fora_catalog_search, thrash_offers, zakaz_next_data
