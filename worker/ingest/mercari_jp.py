"""
Mercari Japan listing checker — deliberately conservative stub.

Mercari Japan has no public API, so this does plain rate-limited HTTP
requests against public search pages: normal headers, a real delay between
requests, and a hard stop (not a retry-harder) on any non-200 response. It
does not attempt to evade rate limiting or bot detection — if Mercari starts
blocking requests, that's a signal to back off, not a problem to route around.

Separately: this is also gated behind MERCARI_JP_SOURCING_APPROVED because
sourcing from a secondhand marketplace in Japan for resale likely requires a
kobutsushō (secondhand dealer) license, which is still an open question. Flip
that env var only once that's actually resolved — the gate is here so the
pipeline doesn't quietly start running against real sourcing volume before
then.
"""

import os
import time

import requests

SEARCH_URL = "https://jp.mercari.com/search"
USER_AGENT = "Mozilla/5.0 (compatible; personal-research-bot/0.1)"


def sourcing_approved() -> bool:
    return os.environ.get("MERCARI_JP_SOURCING_APPROVED", "false").lower() == "true"


def fetch_listings(search_terms: list[str] | None = None) -> list[dict]:
    if not sourcing_approved():
        print(
            "MERCARI_JP_SOURCING_APPROVED is not set to 'true' — skipping Mercari "
            "Japan sourcing. Resolve the kobutsushō/visa question first, then set "
            "this explicitly once you're clear to source secondhand goods."
        )
        return []

    search_terms = search_terms or os.environ.get("MERCARI_JP_SEARCH_TERMS", "").split(",")
    max_requests = int(os.environ.get("MERCARI_JP_MAX_REQUESTS_PER_RUN", "10"))
    delay = float(os.environ.get("MERCARI_JP_DELAY_SECONDS", "5"))

    listings = []
    for i, term in enumerate(t for t in search_terms if t.strip()):
        if i >= max_requests:
            break
        try:
            resp = requests.get(
                SEARCH_URL,
                params={"keyword": term.strip()},
                headers={"User-Agent": USER_AGENT},
                timeout=15,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"Mercari JP request failed for '{term}': {e} — stopping this run.")
            break

        # NOTE: actual HTML parsing intentionally left as a TODO. Mercari's
        # page structure changes often enough that a parser written without
        # a real page in front of you would be guesswork — fill this in once
        # sourcing is approved, against a real fetched page.
        listings.append({"search_term": term, "raw_html": resp.text[:0]})  # placeholder
        time.sleep(delay)

    return listings
