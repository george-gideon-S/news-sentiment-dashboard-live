"""Fetch + normalise RSS feeds into one tidy DataFrame.

feedparser does the heavy lifting -- it swallows malformed XML, weird encodings
and a dozen different date formats so I don't have to hand-roll any of that.
Everything in here is really about *defence*: one dead or glacially slow feed
must never take the whole run down with it. Failures are returned as data, not
raised as exceptions.
"""
from __future__ import annotations

import calendar
import html
import re
import socket
import time
from datetime import datetime, timezone

import feedparser
import pandas as pd

from feeds import FEEDS

# A single slow feed hanging forever is the #1 way an unattended pipeline quietly
# dies at 3am. Cap every network read globally -- feedparser fetches through
# urllib, which honours the default socket timeout.
socket.setdefaulttimeout(25)

# Some feeds 403 a bare urllib user-agent, and WAFs sniff the fingerprint, so
# present as a real browser. The Hindu in particular drops the *first* connection
# (RemoteDisconnected) and only answers on a retry -- hence MAX_TRIES below.
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
MAX_TRIES = 3
RETRY_BACKOFF = 1.5  # seconds * attempt number; a transient drop just needs a beat

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def clean_text(value: str | None) -> str:
    """Strip HTML tags, unescape entities, collapse whitespace.

    RSS summaries routinely carry <img>, <a>, &nbsp; and stray newlines. For a
    headline dashboard I don't need a real HTML parser -- a tag regex plus
    html.unescape is plenty, and a lot cheaper than spinning up BeautifulSoup
    for every one-line string.
    """
    if not value:
        return ""
    text = _TAG_RE.sub(" ", value)
    text = html.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def _published_dt(entry) -> datetime | None:
    """feedparser hands back a UTC struct_time in .published_parsed when it can.
    Not every entry has it, so this is allowed to return None (-> NaT later)."""
    tm = entry.get("published_parsed") or entry.get("updated_parsed")
    if not tm:
        return None
    # struct_time from feedparser is already UTC -> timegm, not mktime.
    return datetime.fromtimestamp(calendar.timegm(tm), tz=timezone.utc)


def _rows_from(parsed, name: str) -> list[dict]:
    now = datetime.now(timezone.utc)
    rows = []
    for e in parsed.entries:
        title = clean_text(e.get("title"))
        if not title:
            continue
        rows.append({
            "source": name,
            "title": title,
            "summary": clean_text(e.get("summary") or e.get("description")),
            "link": e.get("link", ""),
            "published": _published_dt(e),
            "fetched_at": now,
        })
    return rows


def fetch_feed(name: str, url: str) -> tuple[list[dict], dict]:
    """Fetch one feed, retrying transient drops. Returns (rows, report). Never
    raises -- a genuinely dead feed comes back ok=False with the reason, and the
    run carries on without it."""
    report = {"name": name, "url": url, "ok": False, "count": 0,
              "http_status": None, "bozo": None, "error": None, "tries": 0}

    for attempt in range(1, MAX_TRIES + 1):
        report["tries"] = attempt
        parsed = None
        try:
            parsed = feedparser.parse(url, agent=USER_AGENT)
        except Exception as exc:  # RemoteDisconnected, socket timeout, etc.
            report["error"] = f"{type(exc).__name__}: {exc}"

        if parsed is not None:
            report["http_status"] = parsed.get("status")
            report["bozo"] = int(parsed.get("bozo", 0))
            if parsed.entries:
                # bozo=1 only means "not strictly well-formed"; plenty of feeds
                # trip it and still hand over usable entries. Only the truly
                # empty result is a real miss worth retrying.
                rows = _rows_from(parsed, name)
                report["ok"] = True
                report["count"] = len(rows)
                report["error"] = None
                return rows, report
            report["error"] = str(parsed.get("bozo_exception", "no entries"))

        # Transient? Give it a beat and try again. The Hindu needs exactly this.
        if attempt < MAX_TRIES:
            time.sleep(RETRY_BACKOFF * attempt)

    return [], report


def fetch_all(feeds=FEEDS) -> tuple[pd.DataFrame, list[dict]]:
    """Fetch every feed, concat, dedupe. Returns (df, per-feed reports)."""
    all_rows: list[dict] = []
    reports: list[dict] = []
    for feed in feeds:
        rows, report = fetch_feed(feed["name"], feed["url"])
        all_rows.extend(rows)
        reports.append(report)

    df = pd.DataFrame(all_rows)
    if not df.empty:
        # Same headline can show up twice in one pull, and definitely across
        # refreshes. Keep the first sighting per source+title.
        df = df.drop_duplicates(subset=["source", "title"]).reset_index(drop=True)
        df["published"] = pd.to_datetime(df["published"], utc=True, errors="coerce")
    return df, reports


if __name__ == "__main__":
    # Smallest thing that proves the plumbing works: pull and print a handful.
    df, reports = fetch_all()
    for r in reports:
        flag = "ok  " if r["ok"] else "FAIL"
        print(f"[{flag}] {r['name']:<16} http={r['http_status']} "
              f"tries={r['tries']} count={r['count']} {r['error'] or ''}")
    print(f"\nTotal headlines: {len(df)}\n")
    if not df.empty:
        print(df[["source", "title"]].head(5).to_string(index=False))
