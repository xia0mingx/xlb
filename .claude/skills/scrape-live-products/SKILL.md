---
name: scrape-live-products
description: Scrape live skincare products, prices and images from real retailers into the Dewdrop catalog. Covers running an ingest safely, reading its output, verifying the result, and adding a new retailer with the robots.txt gate. Use when asked to pull in live/real product data, refresh prices, or add a retailer.
---

# Scraping live products into the catalog

The pipeline exists and works. Most mistakes here are not code mistakes — they are
running the wrong thing, or declaring success without checking what actually landed.

## Non-negotiables

These are not style preferences. Breaking any of them changes what this project is.

1. **Every request goes through `app/scrapers/fetch.py`.** It enforces robots.txt
   before the request leaves the process. Never bypass it with a bare `httpx` or
   `curl` call to fetch product data — use `fetch()`, `fetch_json()`, `fetch_text()`.
   A one-off probe with `curl` to *inspect* a robots.txt or check a status code is
   fine; fetching catalog content to store is not.
2. **The crawler identifies honestly** as `DewdropSkincareBot`. Do not spoof a browser
   User-Agent to get past a block. A site that wants us gone has said so, and
   claiming to respect robots.txt while disguising ourselves is incoherent.
3. **A retailer that disallows us is not crawled.** Record the exclusion and the
   reason in `EXCLUDED_RETAILERS` in `app/scrapers/registry.py` so the reasoning
   survives. Do not delete those entries.
4. **Dry-run before writing.** Always.

## Running an ingest

From `backend/`:

```bash
# 1. Always first: fetches everything, writes nothing, rolls back at the end.
.venv/Scripts/python.exe -m app.jobs.ingest --limit 10 --dry-run

# 2. Then write.
.venv/Scripts/python.exe -m app.jobs.ingest --limit 10
```

Flags: `--limit N` (products to process), `--dry-run`, `--no-ingredients` (skip
the INCIDecoder lookup), `--no-compare` (skip the second-retailer price search).

**Budget roughly 11 seconds per product.** Per product it makes one Soko Glam
request, two INCIDecoder requests, and up to six Ohlolly requests, all behind a
1.5s per-domain throttle (`scrape_delay_seconds`). 60 products is ~11 minutes.
**Run it in the background** and do other work rather than blocking on it.

`--limit` is a *total*, not a delta: existing products are matched and updated
rather than duplicated. To add 50 new ones on top of 10 existing, pass `--limit 60`
and expect `products_updated: 10, products_created: 50`.

## Reading the output

A normal run looks like this — none of these lines are problems:

```
[6/60] NEW Madecassoside Moisture Sun Serum | sunscreen | $22.0 | img=Y upc=8809936747858 inci=63 concerns=7
        also at ohlolly: $32.0 (upc 1.00)
INFO app.scrapers.incidecoder: no confident incidecoder match for '...' (best score 0.00)
[9/60] NEW PDRN Glow Ampoule | serum | $30.72 | img=Y upc=8803463009687 inci=0 concerns=0
```

What to expect, from an actual 60-product run:

| Signal | Normal | Meaning |
|---|---|---|
| `inci=0 concerns=0` | ~40% of products | No confident INCIDecoder match. Coverage gap, **not an error** — but the product is invisible to the quiz. |
| `size` absent | almost all | Neither retailer publishes a parseable size. Barcode carries matching instead. |
| `also at ohlolly` | ~10% | Cross-retailer match found. Should be `upc 1.00`; a fuzzy match near threshold deserves a look. |
| `skipped` | a few | No price, or fetch failed. Check the reason. |

`img=N` is the one that should be near-zero. A product with no image is dead
weight in the UI, and `discover()` already filters those out — so `img=N` in the
log means the full record lost an image the feed had.

## Verify before declaring success

Do not report a successful ingest from the job's own summary. It reports what it
*wrote*, not whether what it wrote is right. Run:

```bash
.venv/Scripts/python.exe ../.claude/skills/scrape-live-products/verify.py
```

It checks four things that have each caught a real bug:

1. **Out-of-scope products** — non-skincare that got past `is_in_scope()`. A
   baseball cap (`product_type: SWAG`) and four body-care products
   (`product_type: Body`) once landed as `treatment` and `moisturizer`.
2. **Missing or unreachable images** — including CDN URLs that 404.
3. **Duplicate barcodes** — the same GTIN on two canonical products means matching
   failed to recognise them as one SKU.
4. **Orphans** — products with no listing, or listings with no price snapshot.

Then run the tests: `.venv/Scripts/python.exe -m pytest -q`.

If anything out-of-scope landed, fix `is_in_scope()` first, add the case to
`tests/test_ingest_scope.py`, then delete the rows — in that order, so the filter
stops them coming back before you clean up.

## Sharing what you scraped

A scrape lives only in the local `xlb.db`, which is gitignored. Re-scraping is not
reproducible — the feed reorders, prices move, INCIDecoder coverage varies — so a
teammate running `ingest` gets a *different* catalog, and a fresh clone with no
ingest sees an empty one, because synthetic products are hidden.

After a scrape worth sharing, re-dump the fixture and commit it:

```bash
.venv/Scripts/python.exe -m app.jobs.fixture dump   # -> app/data/live_products.json
```

`load` reuses the same upsert helpers as the live ingest, so a fixture product and
a scraped one are indistinguishable in the database. Prices in the file are a
snapshot from dump time, not live; `generated_at` records when.

## Adding a retailer

1. **Read its robots.txt first**, as `DewdropSkincareBot`, and check the *specific
   paths* you need — not just `Disallow: /`. For a Shopify store those are
   `/products.json`, `/products/{handle}.json` and `/search/suggest.json`.
2. If any required path is disallowed, **stop**. Add it to `EXCLUDED_RETAILERS`
   with the reason and move on. Sometimes only part is blocked — YesStyle blocks
   search URLs but permits product pages, which is a sitemap-discovery job, not a
   search-based one. Record that nuance.
3. If it is Shopify, add one `ShopifyRetailer(...)` entry to `SHOPIFY_RETAILERS`.
   Nothing else. One `ShopifyScraper` covers every Shopify store.
4. If it is not Shopify, subclass `RetailerScraper` and implement `search()` and
   `fetch_product()`, returning `ScrapedProduct`. Everything downstream is
   unchanged.
5. Verify the domain resolves without a redirect. `www.ohlolly.com` 301s to
   `ohlolly.com`; `fetch()` follows redirects, but the registry should hold the
   canonical host.
6. Dry-run against it before wiring it into `PRIMARY_RETAILER` or
   `COMPARE_RETAILER` in `jobs/ingest.py`.

## Failure modes

| Symptom | Cause | Action |
|---|---|---|
| `RobotsDisallowed` | robots.txt forbids the path | Do not work around it. Exclude the retailer or use a permitted path. |
| `ScrapeBlocked` | 401/403/407/429/503 | A signal about the retailer, not a parsing bug. Back off; if persistent, add to `EXCLUDED_RETAILERS`. |
| `ScrapeFailed` | network, timeout, unparseable | Usually transient; `fetch()` already retried. |
| `ProductNotFound` | 404 | Handle is stale or guessed. **Take handles from the feed**, never derive them from titles. |
| `IntegrityError: UNIQUE constraint failed: <table>.slug` | upsert matched on display name | Match on the *unique* column. Retailers disagree about casing — `NATURIUM` vs `Naturium` is one brand. |
| Ingest works, UI does not change | the backend did not reload | `uvicorn --reload` is unreliable on Windows here. Restart it. |
| UI suddenly empty | a second, empty `xlb.db` | The SQLite path is relative to the **process working directory**. Run from `backend/`. |

## Where things are

- `app/jobs/ingest.py` — discovery, scope filter, upserts. `is_in_scope()` is the
  scope gate; `classify_category()` is *not* — it falls back to `TREATMENT`.
- `app/scrapers/fetch.py` — the only HTTP path. robots, throttle, retry, exceptions.
- `app/scrapers/registry.py` — retailers, and why excluded ones are excluded.
- `app/scrapers/shopify.py` — covers all Shopify stores.
- `app/scrapers/incidecoder.py` — the ingredient source, since retailers publish none.
- `app/jobs/scheduler.py` — re-prices existing listings; does **not** discover products.
