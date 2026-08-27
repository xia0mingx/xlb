# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All backend commands run from `backend/` and assume the venv at `backend/.venv`.
On Windows use `.venv/Scripts/python.exe`; on macOS/Linux `.venv/bin/python`.

```bash
# Setup
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"

# Run
.venv/Scripts/python.exe -m uvicorn app.main:app --reload   # :8000, /docs for OpenAPI

# Tests
.venv/Scripts/python.exe -m pytest                                    # all (136)
.venv/Scripts/python.exe -m pytest tests/test_matching.py             # one file
.venv/Scripts/python.exe -m pytest -k "allergen"                      # by name
.venv/Scripts/python.exe -m pytest "tests/test_ingest_scope.py::TestInScope::test_accepted"

# Data
.venv/Scripts/python.exe -m app.jobs.seed --reset          # tables + synthetic catalog
.venv/Scripts/python.exe -m app.jobs.ingest --limit 10 --dry-run   # live, writes nothing
.venv/Scripts/python.exe -m app.jobs.ingest --limit 10             # live, writes
.venv/Scripts/python.exe -m app.jobs.fixture load          # shared live catalog from JSON
.venv/Scripts/python.exe -m app.jobs.fixture dump          # DB -> app/data/live_products.json
```

`fixture load` is what a fresh clone needs: synthetic products are hidden by
default, so without it the catalog is empty. `xlb.db` is gitignored, and a live
catalog is shared as JSON rather than as a database file — re-scraping is not
reproducible, since the feed reorders and prices move between runs.

```bash
# Frontend, from frontend/
npm install
npm run dev        # :5173, proxies /api -> 127.0.0.1:8000
npm run build      # tsc -b && vite build
npx tsc -b         # typecheck only
```

`pytest` is configured with `asyncio_mode = "auto"`, so async tests need no
decorator. **There is no linter or formatter configured** — the `# noqa`
comments are conventional, not enforced. There are no frontend tests.

### Environment gotchas

- **`uvicorn --reload` is unreliable on Windows here.** It has repeatedly failed
  to fire for newly added files, and has logged `Reloading...` then hung with the
  old worker still serving. If a change appears not to apply, restart the server
  before debugging the code.
- The SQLite path in `config.py` is `sqlite+aiosqlite:///./xlb.db` — **relative to
  the process working directory**, not the package. Launching uvicorn from the
  repo root instead of `backend/` silently creates a second, empty `xlb.db` and
  `create_all` populates it with empty tables, so the UI looks empty rather than
  erroring.
- `backend/.env` drives the chat assistant (see `.env.example`). With
  `LLM_BASE_URL`, `LLM_MODEL` or `OPENCODE_API_KEY` unset, `/api/chat/status`
  returns `{"enabled": false}` by design — the config deliberately has no
  defaults so an unset key fails loudly rather than pointing somewhere wrong.

## Architecture

Skincare price comparison, ingredient analysis, and quiz-driven recommendation.
FastAPI + SQLAlchemy 2.0 async + SQLite (Postgres via `DATABASE_URL`); React 18 +
TypeScript + Vite + MUI.

**Scope is deliberately narrow: facial skincare only.** Makeup, haircare,
fragrance, body care and merchandise are out — they need a different attribute
model and none of the ingredient-driven features transfer. Enforcing this matters
in practice; see `is_in_scope()` below.

### The price-comparison data model

Three tables carry the core idea, and the distinction between them is load-bearing:

- **`product`** — the canonical real-world SKU, independent of retailer.
- **`listing`** — that product as sold at one retailer.
- **`price_snapshot`** — append-only observation of a listing's price. This is
  what makes history charts and "lowest in 90 days" possible; never update a
  price in place.

### Matching is the correctness-critical path

`services/matching.py` decides whether a listing at retailer A is the same SKU as
one at retailer B. Getting it wrong shows a user the wrong price, which is worse
than showing none — so listings below `match_confidence_threshold` (0.85) are
stored but flagged `needs_review` and hidden from the public price table.

Order: identical barcode → confidence 1.0. Otherwise fuzzy brand+name, **gated**
on size and pack count. `sizes_match()` is permissive when either side is unknown
(most listings omit size) but a hard no when both are known and differ.

`classify_category()` is **a classifier, not a gatekeeper** — it falls back to
`TREATMENT` for anything unrecognized. Scope must therefore be decided before
classification, which is what `is_in_scope()` in `jobs/ingest.py` does. The
retailer's own `product_type` is the reliable signal there: Soko Glam files its
entire body range as `Body` and merchandise as `SWAG`.

### Ingredient analysis feeds everything else

`services/inci.py` parses and canonicalizes raw INCI text; `services/analysis.py`
turns an ordered name list into an `Analysis` (actives, irritants, active groups,
comedogenic max, fragrance/alcohol/essential-oil flags). INCI **order is
preserved throughout** because position approximates concentration — that is what
makes `group_weight()`, dupe scoring and recommendation weighting meaningful
rather than flat set comparison.

`data/conflicts.json` is the single source of rule data: `concerns`,
`concern_ingredients`, `skin_type_preferences`, `conflict_rules`. Recommendation
(`services/recommend.py`) is rule-based and additive on purpose — every point
traces to a named ingredient, so the UI can always answer "why am I shown this?".
A black-box ranker would be worse here even if it ranked better.

Note the two-layer ingredient story: `Ingredient` rows exist for **every** INCI
name encountered, including ones the dictionary has never heard of, so a product
page can render its full list. Enrichment happens at analysis time via
`lookup()`, and `analyze()` marks unknowns rather than failing.

### `product_query()` is the single product-read chokepoint

Everything that reads products goes through `product_query()` in `api/deps.py` —
list, deals, detail, dupes, quiz, and the chat tools. It excludes **synthetic seed
products** by default, identified by the `seed-` prefix on `Retailer.scraper_key`.
Filtering in one place is what stops synthetic rows leaking into one surface after
being hidden from another. Override with `SHOW_SYNTHETIC_PRODUCTS=true`.

The marker is derived rather than stored: an `is_synthetic` column would need a
migration, and Alembic is declared as a dependency but **not wired up** — the
schema is created by `create_all` on startup. Anything requiring a schema change
has to account for that.

### Scraping

`scrapers/fetch.py` is the only HTTP path, and it enforces robots.txt **before
the request leaves the process**, plus per-domain throttling and retry. Status
codes become distinct exception types so callers can tell "blocked" (a signal
about the retailer) from "broken" (a bug in parsing). The crawler identifies
honestly as `DewdropSkincareBot` rather than spoofing a browser.

`registry.py` records retailers **and why excluded ones were excluded** — keep
that reasoning when touching it. Adding a Shopify retailer is one registry entry;
one `ShopifyScraper` covers all of them.

Retailers do not publish ingredients — 0 of 40 sampled products had an extractable
INCI list — so `scrapers/incidecoder.py` is the ingredient source, not a fallback.
It matches roughly half of products; the rest legitimately land with no INCI list
and no concerns, and are invisible to the quiz. That is a coverage gap, not a bug.

### Two jobs, different purposes

- `jobs/seed.py` — invents a synthetic catalog with 90 days of generated price
  history. Deterministic (fixed RNG seed) so screenshots and tests stay stable.
- `jobs/ingest.py` — discovers real SKUs, images and prices. Idempotent: matches
  on barcode then slug, and **commits per product** so one bad row late in a long
  throttled run cannot discard everything already fetched.
- `jobs/scheduler.py` — re-prices existing listings only; it does not discover
  products. Off unless `enable_scheduler`.

When upserting anything, match on the **unique** column, not the display name.
Both `brand.slug` and `ingredient.inci_name` are unique, and retailers disagree
about casing and spelling (`NATURIUM` vs `Naturium`), so name-based lookups pass
and then violate the constraint.

### Allergen screening — two modules, don't confuse them

- **`services/allergens.py`** — the REST API path. Used by `api/deps.py`,
  `products.py` and `quiz.py`.
- **`chat/allergens.py`** — the chat assistant's own enforcement layer.

Two properties make the service more than a substring search, and both are worth
preserving. **Group expansion**: someone who says "fragrance" means the class, so
a group term expands to every member named in `conflicts.json` — a product
declaring `Linalool` and `Limonene` but never "Parfum" is exactly the case that
catches people out. **Honest negatives**: `unknown_count` is carried into the
verdict, so a product whose list could not be fully identified is never reported
as clear.

Allergen membership lives in `conflicts.json`, deliberately *not* as an ingredient
dictionary flag — `is_irritant` already means "this stings" (kojic acid is flagged
and is not an allergen), and overloading it would conflate the two.

In the quiz, **an allergy is a filter, not a penalty**: matching products are
dropped in the route before scoring, rather than pushed down the ranking. That
also keeps `score_product`'s contract intact — every point it awards still traces
to an ingredient's effect on skin.

### Chat assistant

`app/chat/` is an agentic loop against an OpenAI-compatible endpoint. The
architectural rule: **safety-critical behavior is enforced in code, never in the
prompt.** `allergens.py` filters every product list before the model sees it, and
exposes no parameter the model can use to relax the filter — an assistant that
"forgets" a stated allergy is the one failure this feature cannot have. The tools
in `tools.py` reuse the same services the REST API uses, so chat answers and page
answers cannot disagree. The loop is bounded three ways (round cap, timeout,
trimmed history) because an unbounded loop against a paid endpoint is a billing
incident waiting to happen.

## Conventions

Comments explain **why**, especially where a choice looks wrong without context —
the existing code is dense with rationale for non-obvious decisions and load-bearing
constraints. Match that. Do not add comments restating what the code says.

Prefer honest failure over silent plausibility: a stale price shown with a
timestamp beats a hidden one, an unresolved allergen term is reported rather than
dropped, and a low-confidence match is hidden rather than displayed.
