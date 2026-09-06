import os
import psycopg2
import psycopg2.extras


def get_connection():
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=os.environ.get("POSTGRES_PORT", "5432"),
        dbname=os.environ.get("POSTGRES_DB", "resale"),
        user=os.environ.get("POSTGRES_USER", "resale"),
        password=os.environ.get("POSTGRES_PASSWORD", "changeme"),
    )


def upsert_listing(conn, source_name: str, listing: dict):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM sources WHERE name = %s", (source_name,))
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"unknown source: {source_name}")
        source_id = row[0]

        cur.execute(
            """
            INSERT INTO listings
                (source_id, external_id, title, brand, model, condition,
                 price_amount, currency, url, raw, last_seen)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (source_id, external_id) DO UPDATE SET
                price_amount = EXCLUDED.price_amount,
                status = 'active',
                last_seen = now()
            RETURNING id
            """,
            (
                source_id,
                listing["external_id"],
                listing.get("title"),
                listing.get("brand"),
                listing.get("model"),
                listing.get("condition"),
                listing.get("price_amount"),
                listing.get("currency", "USD"),
                listing.get("url"),
                psycopg2.extras.Json(listing.get("raw", {})),
            ),
        )
        listing_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO price_snapshots (listing_id, price_amount, currency, status)
            VALUES (%s, %s, %s, 'active')
            """,
            (listing_id, listing.get("price_amount"), listing.get("currency", "USD")),
        )
    conn.commit()
    return listing_id
