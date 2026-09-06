"""
BDroppy / BrandsDistribution product feed ingestion.

BDroppy is a real B2B dropship feed (XML), not a scrape target — but it
requires a signed reseller agreement to get a feed URL + API key. Until
BDROPPY_FEED_URL is set in .env, this reads a local sample XML file instead
so the rest of the pipeline is testable now.

Once you have real credentials: set BDROPPY_FEED_URL / BDROPPY_API_KEY in
.env and confirm the actual field names/structure against the feed
documentation they send you — this parser's tag names are a reasonable guess
at a typical fashion-dropship XML feed, not verified against BDroppy's real
schema yet.
"""

import os
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

SAMPLE_FEED_PATH = Path(__file__).parent.parent.parent / "sample_data" / "sample_bdroppy_feed.xml"


def fetch_feed_xml() -> str:
    feed_url = os.environ.get("BDROPPY_FEED_URL")
    if not feed_url:
        print("BDROPPY_FEED_URL not set — using local sample feed for testing.")
        return SAMPLE_FEED_PATH.read_text()

    api_key = os.environ.get("BDROPPY_API_KEY", "")
    resp = requests.get(feed_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_feed(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    listings = []
    for product in root.findall(".//product"):
        listings.append(
            {
                "source": "bdroppy",
                "external_id": product.findtext("sku", default=""),
                "title": product.findtext("name", default=""),
                "brand": product.findtext("brand", default=""),
                "model": product.findtext("model", default="")
                or product.findtext("name", default=""),
                "condition": "new",  # BDroppy sells new overstock, not secondhand
                "price_amount": float(product.findtext("wholesale_price", default="0") or 0),
                "currency": product.findtext("currency", default="EUR"),
                "url": product.findtext("product_url", default=""),
                "raw": {child.tag: child.text for child in product},
            }
        )
    return listings


def fetch_listings() -> list[dict]:
    return parse_feed(fetch_feed_xml())


if __name__ == "__main__":
    import json

    print(json.dumps(fetch_listings(), indent=2))
