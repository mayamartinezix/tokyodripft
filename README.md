# Resale Arbitrage Notifier — home lab scaffold

Two-laptop layout:
- **DB laptop**: Postgres + ntfy (notifications). `docker/docker-compose.core.yml`
- **Ingestion laptop**: the worker container that pulls listings, matches items, prices
  them, and pushes notifications. `docker/docker-compose.worker.yml`

## Status of the two sourcing channels (as of this build)

- **BDroppy / BrandsDistribution**: no reseller agreement yet, so `worker/ingest/bdroppy_feed.py`
  is wired to read a **local sample XML file** by default. Once your reseller
  application is approved and you have a feed URL + API key, drop them into
  `.env` and it'll pull the real feed instead.
- **Mercari Japan / LuxeWholesale**: put on hold pending the kobutsushō
  (secondhand dealer) license / visa-eligibility question. `worker/ingest/mercari_jp.py`
  exists as a deliberately conservative, low-volume stub — **don't point it at
  real sourcing volume until that's resolved.** LuxeWholesale isn't wired up at
  all yet since its access model (direct license vs. via Buyee) still needs
  clarifying with them directly.

Because of that, everything downstream (matching, fee-netting pricing engine,
notifications) is built and testable today against **sample data**
(`sample_data/sample_listings.json`), so you're not blocked on either pending
item to develop and test the core logic.

## Fee assumptions

`worker/config/fees.yaml` holds the eBay and Vestiaire Collective fee
schedules used to net out your real margin. These are current-as-of-2026
figures pulled from public seller guides, **not** pulled live from either
platform — both change their fee structures periodically, so sanity-check
against your own seller dashboard before trusting a suggested price.

## Running it

```bash
cd worker
pip install -r requirements.txt
cp ../.env.example ../.env   # fill in what you have; sample mode works with defaults
python main.py --sample      # runs the full pipeline against sample_data/, prints
                              # opportunities and sends a test ntfy notification
```

For the real deployment: bring up `docker/docker-compose.core.yml` on the DB
laptop, set `POSTGRES_HOST` / `NTFY_URL` in `.env` on the ingestion laptop to
that machine's LAN IP, then bring up `docker/docker-compose.worker.yml` there.
`worker/main.py` (no `--sample`) runs on a schedule via APScheduler — interval
configured in `.env`.

## What's intentionally NOT here

No auto-bid / auto-purchase. This pipeline stops at "here's a promising item
and a suggested price" — actually buying or listing is a manual step. No
anti-bot-detection tooling for Mercari — the stub does plain, rate-limited
requests and backs off on failure rather than escalating around blocks.
