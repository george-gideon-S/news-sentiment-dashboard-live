"""Orchestration: fetch -> sentiment -> topics -> cache.

This is the bit you'd hang off a cron job in production. The dashboard never
scrapes on its own; it just reads whatever this last wrote into data/. That
split -- producer writes the cache, the UI only reads it -- is what keeps the
dashboard snappy and stops it hammering the feeds every time someone wiggles a
filter.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from scrape import fetch_all
from sentiment import add_sentiment
from topics import add_topics

DATA_DIR = Path(__file__).parent / "data"
HEADLINES_CSV = DATA_DIR / "headlines.csv"
META_JSON = DATA_DIR / "run_meta.json"


def run() -> tuple[pd.DataFrame, dict]:
    """Run the whole pipeline once and persist the results to data/."""
    DATA_DIR.mkdir(exist_ok=True)
    df, reports = fetch_all()
    df = add_sentiment(df)
    df = add_topics(df)

    meta = {
        "last_run": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total": int(len(df)),
        "feeds": reports,
    }

    # Only overwrite the cache if we actually got something. If every feed is
    # down (no network), keep the last good pull around for the dashboard.
    if not df.empty:
        df.to_csv(HEADLINES_CSV, index=False)
    META_JSON.write_text(json.dumps(meta, indent=2))
    return df, meta


def load_cache() -> tuple[pd.DataFrame, dict]:
    """Read the last persisted run. Empty frame if nothing's been written yet."""
    if HEADLINES_CSV.exists():
        df = pd.read_csv(HEADLINES_CSV)
        for col in ("published", "fetched_at"):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")
    else:
        df = pd.DataFrame()
    meta = json.loads(META_JSON.read_text()) if META_JSON.exists() else {}
    return df, meta


if __name__ == "__main__":
    df, meta = run()
    print(f"Run at {meta['last_run']}")
    for r in meta["feeds"]:
        flag = "ok  " if r["ok"] else "FAIL"
        print(f"  [{flag}] {r['name']:<16} http={r['http_status']} "
              f"count={r['count']} {r['error'] or ''}")
    print(f"\nTotal headlines: {len(df)}")
    if not df.empty:
        print("Sentiment mix:", df["sent_label"].value_counts().to_dict())
        print("\nTop topics:")
        print(df["topic"].value_counts().head(10).to_string())
        print("\nSample:")
        print(df[["source", "sent_label", "sent_compound", "topic", "title"]]
              .head(8).to_string(index=False))
