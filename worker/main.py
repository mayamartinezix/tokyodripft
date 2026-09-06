"""
Orchestrates one pass of: ingest buy-side listings -> match against sell-side
comps -> price -> notify on anything that clears your target margin.

Sell-side comp data (eBay / Vestiaire) isn't wired up as a live feed yet —
eBay's sold-listing data requires restricted Marketplace Insights API access
(needs eBay approval, not guaranteed), and Vestiaire has no public API and
actively blocks scrapers. Realistic interim approach: maintain a comps file
yourself (export from eBay's own "sold listings" search periodically) and
point SELL_COMPS_PATH at it. Swap in a real feed later if you get API access.

Usage:
    python main.py --sample     # runs once against sample_data/, prints results
    python main.py              # runs on a schedule against real config
"""

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

import matcher
import notify
import pricing
from ingest import bdroppy_feed, mercari_jp
# `db` (psycopg2) is only needed for the real scheduled run against Postgres,
# not for --sample mode — imported lazily inside run_scheduled_pass so
# --sample works without a psycopg2 install / a running database.

BASE_DIR = Path(__file__).parent.parent
SAMPLE_COMPS_PATH = BASE_DIR / "sample_data" / "sample_sell_comps.json"


def load_sell_comps(path: Path) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def comps_by_source(comps: list[dict]) -> dict:
    by_source = {}
    for c in comps:
        by_source.setdefault(c["source"], []).append(c)
    return by_source


def run_once(buy_listings: list[dict], sell_comps: list[dict], notify_enabled: bool = True):
    groups = matcher.group_listings(buy_listings, sell_comps)

    for group in groups:
        buy = group["buy"]
        comps = group["comps"]
        if not comps:
            continue

        comp_prices_by_source = {}
        for source, items in comps_by_source(comps).items():
            comp_prices_by_source[source] = [c["price_amount"] for c in items]

        result = pricing.evaluate_opportunity(
            buy_price=buy["price_amount"],
            comp_prices=comp_prices_by_source,
        )
        if not result:
            continue

        best = result["by_source"][result["best_sell_source"]]
        print(f"\n--- {buy.get('title')} ---")
        print(f"  buy price: {buy['price_amount']}")
        print(json.dumps(result, indent=2))

        if notify_enabled and best["meets_target_margin"]:
            notify.send_opportunity_alert(buy.get("title", "item"), result)


def run_sample():
    buy_listings = bdroppy_feed.fetch_listings()  # falls back to sample XML automatically
    sell_comps = load_sell_comps(SAMPLE_COMPS_PATH)
    run_once(buy_listings, sell_comps, notify_enabled=False)
    print("\n(sample mode — notifications suppressed; drop --sample to send real alerts)")


def run_scheduled_pass():
    import db  # lazy import — see note above

    buy_listings = []
    buy_listings += bdroppy_feed.fetch_listings()
    buy_listings += mercari_jp.fetch_listings()

    conn = db.get_connection()
    try:
        for listing in buy_listings:
            db.upsert_listing(conn, listing.get("source", "bdroppy"), listing)
    finally:
        conn.close()

    comps_path = Path(os.environ.get("SELL_COMPS_PATH", SAMPLE_COMPS_PATH))
    sell_comps = load_sell_comps(comps_path)

    run_once(buy_listings, sell_comps, notify_enabled=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", action="store_true", help="run once against sample data")
    args = parser.parse_args()

    load_dotenv(BASE_DIR / ".env")

    if args.sample:
        run_sample()
        return

    from apscheduler.schedulers.blocking import BlockingScheduler

    interval = int(os.environ.get("RUN_INTERVAL_MINUTES", "60"))
    scheduler = BlockingScheduler()
    scheduler.add_job(run_scheduled_pass, "interval", minutes=interval, next_run_time=None)
    print(f"Starting scheduler — running every {interval} minutes. Ctrl+C to stop.")
    run_scheduled_pass()  # run once immediately, then on schedule
    scheduler.start()


if __name__ == "__main__":
    main()
