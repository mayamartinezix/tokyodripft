"""Thin wrapper around a self-hosted ntfy instance (runs on the DB laptop)."""

import os
import requests


def send_opportunity_alert(item_title: str, opportunity: dict) -> bool:
    ntfy_url = os.environ.get("NTFY_URL")
    if not ntfy_url:
        print("NTFY_URL not set — skipping notification, printing instead:")
        print(item_title, opportunity)
        return False

    best = opportunity["by_source"][opportunity["best_sell_source"]]
    message = (
        f"Buy: {item_title}\n"
        f"Sell on: {opportunity['best_sell_source']}\n"
        f"Suggested sell price: {best['suggested_sell_price']}\n"
        f"Suggested max buy price: {best['suggested_buy_max_for_target_margin']}\n"
        f"Estimated profit: {best['estimated_profit_at_this_buy_price']} "
        f"({best['estimated_margin_pct']:.0%} margin)"
    )

    try:
        resp = requests.post(
            ntfy_url,
            data=message.encode("utf-8"),
            headers={
                "Title": f"Opportunity: {item_title}"[:200],
                "Priority": "default",
                "Tags": "moneybag",
            },
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"ntfy send failed: {e}")
        return False
