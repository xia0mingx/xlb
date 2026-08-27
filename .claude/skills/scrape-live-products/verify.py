"""Post-ingest verification for the live catalog.

The ingest job's summary reports what it wrote, not whether what it wrote is
right. Each check here corresponds to a bug that actually reached the database.

    python .claude/skills/scrape-live-products/verify.py
    python .claude/skills/scrape-live-products/verify.py --check-images
    python .claude/skills/scrape-live-products/verify.py --db backend/xlb.db

Exits 1 if any check fails, so it can gate a workflow.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

# Import the real scope filter rather than reimplementing it: a copy here would
# drift from the one the ingest job actually applies, and then this script would
# certify rows the job would now reject.
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "backend"))

try:
    from app.jobs.ingest import is_in_scope
except Exception as exc:  # noqa: BLE001 - a missing venv is a normal local state
    print(f"! cannot import app.jobs.ingest ({exc})")
    print("  run this with backend/.venv's python, from the repo root")
    raise SystemExit(2) from None

LIVE_ONLY = """
    p.id IN (
        SELECT l.product_id FROM listing l
        JOIN retailer r ON r.id = l.retailer_id
        WHERE r.scraper_key NOT LIKE 'seed-%'
    )
"""


def _rows(conn: sqlite3.Connection, sql: str, *args) -> list[tuple]:
    return list(conn.execute(sql, args))


def check_scope(conn: sqlite3.Connection) -> list[str]:
    """Non-skincare that got past is_in_scope().

    Checked on title alone: product_type is not stored, so this is the weaker of
    the two signals the job uses. It still catches the cases that have slipped
    through, and a hit here means the filter needs a product_type entry too.
    """
    failures = []
    for pid, name, category in _rows(
        conn, f"SELECT p.id, p.name, p.category FROM product p WHERE {LIVE_ONLY}"
    ):
        if not is_in_scope(None, name):
            failures.append(f"#{pid} [{category}] {name}")
    return failures


def check_images(conn: sqlite3.Connection) -> list[str]:
    return [
        f"#{pid} {name}"
        for pid, name in _rows(
            conn,
            f"SELECT p.id, p.name FROM product p "
            f"WHERE {LIVE_ONLY} AND (p.image_url IS NULL OR p.image_url = '')",
        )
    ]


def check_duplicate_barcodes(conn: sqlite3.Connection) -> list[str]:
    """Two canonical products sharing a GTIN means matching missed a duplicate."""
    return [
        f"upc {upc} on {n} products: {names}"
        for upc, n, names in _rows(
            conn,
            "SELECT upc, COUNT(*) n, GROUP_CONCAT(name, ' | ') FROM product "
            "WHERE upc IS NOT NULL AND upc != '' GROUP BY upc HAVING n > 1",
        )
    ]


def check_orphans(conn: sqlite3.Connection) -> list[str]:
    problems = [
        f"product #{pid} {name}: no listing"
        for pid, name in _rows(
            conn,
            "SELECT id, name FROM product p WHERE NOT EXISTS "
            "(SELECT 1 FROM listing l WHERE l.product_id = p.id)",
        )
    ]
    problems += [
        f"listing #{lid} ({sku}): no price snapshot"
        for lid, sku in _rows(
            conn,
            "SELECT l.id, l.retailer_sku FROM listing l "
            "JOIN retailer r ON r.id = l.retailer_id "
            "WHERE r.scraper_key NOT LIKE 'seed-%' AND NOT EXISTS "
            "(SELECT 1 FROM price_snapshot s WHERE s.listing_id = l.id)",
        )
    ]
    return problems


def check_image_urls_resolve(conn: sqlite3.Connection, limit: int) -> list[str]:
    """Fetch each image URL. Off by default: it is slow and hits the CDN."""
    try:
        import httpx
    except ImportError:
        return ["httpx not installed, cannot check image URLs"]

    urls = _rows(
        conn,
        f"SELECT p.id, p.name, p.image_url FROM product p "
        f"WHERE {LIVE_ONLY} AND p.image_url IS NOT NULL LIMIT ?",
        limit,
    )
    failures = []
    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        for pid, name, url in urls:
            try:
                response = client.head(url)
                if response.status_code >= 400:
                    failures.append(f"#{pid} {name}: HTTP {response.status_code}")
            except httpx.HTTPError as exc:
                failures.append(f"#{pid} {name}: {type(exc).__name__}")
    return failures


def summary(conn: sqlite3.Connection) -> None:
    live = conn.execute(
        f"SELECT COUNT(*) FROM product p WHERE {LIVE_ONLY}"
    ).fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM product").fetchone()[0]
    with_inci = conn.execute(
        f"SELECT COUNT(*) FROM product p WHERE {LIVE_ONLY} AND EXISTS "
        "(SELECT 1 FROM product_ingredient pi WHERE pi.product_id = p.id)"
    ).fetchone()[0]
    # Real retailers only. Counting every listing would fold in the synthetic
    # products, which each carry 2-4 fictional retailers and would report ~50
    # comparable products where there are 6.
    multi = conn.execute(
        "SELECT COUNT(*) FROM (SELECT l.product_id FROM listing l "
        "JOIN retailer r ON r.id = l.retailer_id "
        "WHERE r.scraper_key NOT LIKE 'seed-%' "
        "GROUP BY l.product_id HAVING COUNT(DISTINCT l.retailer_id) > 1)"
    ).fetchone()[0]

    print("catalog")
    print(f"  live products      {live}")
    print(f"  synthetic          {total - live}")
    print(f"  live with INCI     {with_inci}"
          f"{f' ({with_inci * 100 // live}%)' if live else ''}")
    print(f"  multi-retailer     {multi}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=None, help="path to xlb.db")
    parser.add_argument(
        "--check-images", action="store_true", help="also fetch image URLs (slow)"
    )
    parser.add_argument("--image-limit", type=int, default=25)
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else REPO_ROOT / "backend" / "xlb.db"
    if not db_path.exists():
        print(f"! no database at {db_path}")
        return 2

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    print(f"verifying {db_path}\n")
    summary(conn)

    checks = [
        ("out-of-scope products", check_scope(conn)),
        ("products with no image", check_images(conn)),
        ("duplicate barcodes", check_duplicate_barcodes(conn)),
        ("orphaned rows", check_orphans(conn)),
    ]
    if args.check_images:
        checks.append(
            ("unreachable image URLs", check_image_urls_resolve(conn, args.image_limit))
        )

    failed = 0
    for label, problems in checks:
        if problems:
            failed += 1
            print(f"FAIL  {label} ({len(problems)})")
            for problem in problems[:15]:
                print(f"        {problem}")
            if len(problems) > 15:
                print(f"        ... and {len(problems) - 15} more")
        else:
            print(f"ok    {label}")

    print()
    if failed:
        print(f"{failed} check(s) failed")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
