"""
Fee-aware pricing engine.

Given a set of comparable sell-side prices (what similar items have sold or
listed for on eBay / Vestiaire), and a candidate buy-side price, this figures
out:
  - net payout after platform fees for a given gross sale price
  - a suggested sell price (based on comps)
  - the maximum you could pay on the buy side and still hit your target margin
"""

import os
import statistics
import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config" / "fees.yaml"


def load_fee_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def ebay_net_payout(gross_sale_amount: float, cfg: dict) -> float:
    ebay = cfg["ebay"]
    threshold = ebay["threshold_amount"]
    if gross_sale_amount <= threshold:
        fee = gross_sale_amount * ebay["final_value_fee_pct"]
    else:
        fee = threshold * ebay["final_value_fee_pct"] + (
            gross_sale_amount - threshold
        ) * ebay["final_value_fee_pct_over_threshold"]

    per_order_fee = (
        ebay["per_order_fee_low"]
        if gross_sale_amount <= ebay["per_order_fee_low_max_amount"]
        else ebay["per_order_fee_high"]
    )
    return round(gross_sale_amount - fee - per_order_fee, 2)


def vestiaire_net_payout(gross_sale_amount: float, cfg: dict) -> float:
    vest = cfg["vestiaire"]
    pct = vest["tiers"][-1]["pct"]  # default to top (uncapped) tier
    for tier in vest["tiers"]:
        if tier["max_amount"] is None or gross_sale_amount <= tier["max_amount"]:
            pct = tier["pct"]
            break
    commission = gross_sale_amount * pct
    processing = (
        gross_sale_amount * vest["payment_processing_pct"]
        + vest["payment_processing_flat"]
    )
    return round(gross_sale_amount - commission - processing, 2)


NET_PAYOUT_FUNCS = {
    "ebay": ebay_net_payout,
    "vestiaire": vestiaire_net_payout,
}


def suggested_sell_price(comp_prices: list[float]) -> float:
    """Simple comp-based suggestion: median of recent comparable sale/listing
    prices. Swap in a trimmed mean or sell-through-weighted average once you
    have enough real sold-price history to make that worthwhile."""
    if not comp_prices:
        raise ValueError("need at least one comparable price")
    return round(statistics.median(comp_prices), 2)


def max_buy_price_for_target_margin(
    sell_price: float, target_source: str, target_margin_pct: float, cfg: dict
) -> float:
    """Working backward from a sell price and a target margin, what's the
    most you can pay on the buy side (plus assume a flat shipping/handling
    cost you supply separately) and still hit that margin?"""
    net_func = NET_PAYOUT_FUNCS[target_source]
    net = net_func(sell_price, cfg)
    max_cost = net / (1 + target_margin_pct)
    return round(max_cost, 2)


def evaluate_opportunity(
    buy_price: float,
    comp_prices: dict,  # e.g. {"ebay": [120, 135, 110], "vestiaire": [150, 140]}
    shipping_cost: float = 0.0,
    target_margin_pct: float | None = None,
) -> dict:
    cfg = load_fee_config()
    target_margin_pct = target_margin_pct or float(
        os.environ.get("TARGET_MIN_MARGIN_PCT", cfg["pricing"]["target_min_margin_pct"])
    )

    results = {}
    for source, prices in comp_prices.items():
        if source not in NET_PAYOUT_FUNCS or not prices:
            continue
        sell_price = suggested_sell_price(prices)
        net_payout = NET_PAYOUT_FUNCS[source](sell_price, cfg)
        total_cost = buy_price + shipping_cost
        profit = round(net_payout - total_cost, 2)
        margin_pct = round(profit / total_cost, 4) if total_cost else None
        buy_max = max_buy_price_for_target_margin(
            sell_price, source, target_margin_pct, cfg
        )
        results[source] = {
            "suggested_sell_price": sell_price,
            "net_payout": net_payout,
            "estimated_profit_at_this_buy_price": profit,
            "estimated_margin_pct": margin_pct,
            "meets_target_margin": margin_pct is not None and margin_pct >= target_margin_pct,
            "suggested_buy_max_for_target_margin": buy_max,
        }

    if not results:
        return {}

    best_source = max(
        results, key=lambda s: results[s]["estimated_profit_at_this_buy_price"]
    )
    return {"best_sell_source": best_source, "by_source": results}


if __name__ == "__main__":
    # quick sanity check
    out = evaluate_opportunity(
        buy_price=150.0,
        comp_prices={"ebay": [280, 265, 300], "vestiaire": [320, 310]},
        shipping_cost=15.0,
    )
    import json

    print(json.dumps(out, indent=2))
