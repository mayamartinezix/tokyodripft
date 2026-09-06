"""
Cross-platform item matching.

Titles differ a lot between a wholesale feed, Mercari Japan, eBay, and
Vestiaire — this does basic normalization + fuzzy title matching so listings
of "the same bag" can be grouped even when the exact wording differs. This is
a starting point, not a solved problem: expect to tune it once you're looking
at real listings, and consider adding image-similarity matching later since
bag titles are especially inconsistent across platforms.
"""

import difflib
import re

CONDITION_BUCKETS = {
    "new": ["new", "nwt", "brand new", "未使用", "新品"],
    "excellent": ["excellent", "like new", "美品"],
    "good": ["good", "used", "良い", "中古"],
    "fair": ["fair", "worn", "damaged", "傷"],
}


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def bucket_condition(raw_condition: str) -> str:
    normalized = normalize_text(raw_condition or "")
    for bucket, keywords in CONDITION_BUCKETS.items():
        if any(kw in normalized for kw in keywords):
            return bucket
    return "unknown"


def title_similarity(title_a: str, title_b: str) -> float:
    return difflib.SequenceMatcher(
        None, normalize_text(title_a), normalize_text(title_b)
    ).ratio()


def is_likely_match(
    listing_a: dict, listing_b: dict, title_threshold: float = 0.55
) -> bool:
    """listing dicts expected to have: brand, model, condition, title"""
    if listing_a.get("brand") and listing_b.get("brand"):
        if normalize_text(listing_a["brand"]) != normalize_text(listing_b["brand"]):
            return False

    if bucket_condition(listing_a.get("condition", "")) != bucket_condition(
        listing_b.get("condition", "")
    ):
        # condition mismatch doesn't rule out a match on its own — a buy-side
        # listing might just describe condition less precisely — but it
        # raises the bar for title similarity.
        title_threshold += 0.15

    sim = title_similarity(
        listing_a.get("model") or listing_a.get("title", ""),
        listing_b.get("model") or listing_b.get("title", ""),
    )
    return sim >= title_threshold


def group_listings(buy_listings: list[dict], sell_comp_listings: list[dict]) -> list[dict]:
    """For each buy-side listing, find sell-side comps that look like the same
    item. Returns a list of {"buy": listing, "comps": [listing, ...]}."""
    groups = []
    for buy in buy_listings:
        comps = [
            sell for sell in sell_comp_listings if is_likely_match(buy, sell)
        ]
        groups.append({"buy": buy, "comps": comps})
    return groups
