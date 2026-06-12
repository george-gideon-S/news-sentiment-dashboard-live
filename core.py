"""Lean, self-contained scrape + sentiment + topic engine for the Vercel build.

Same logic as the Streamlit pipeline (scrape.py / sentiment.py / topics.py),
collapsed into one dependency-light module: feedparser + vaderSentiment only,
no pandas. The web frontend does all the aggregation in JS, so this just needs
to emit clean per-headline records.

Imported by BOTH api/refresh.py (live re-scrape) and build_data.py (the
committed data.json snapshot), so the two paths can never drift in schema.
"""
from __future__ import annotations

import calendar
import html
import re
import socket
import time
from datetime import datetime, timezone

import feedparser
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

FEEDS = [
    {"name": "BBC",            "url": "http://feeds.bbci.co.uk/news/rss.xml"},
    {"name": "Times of India", "url": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms"},
    {"name": "Al Jazeera",     "url": "https://www.aljazeera.com/xml/rss/all.xml"},
    {"name": "The Hindu",      "url": "https://www.thehindu.com/news/feeder/default.rss"},
    {"name": "NPR",            "url": "https://feeds.npr.org/1001/rss.xml"},
]

# Browser-ish UA + short timeouts + a single retry. Tighter than the Streamlit
# pipeline because this runs in a serverless function with a wall-clock budget.
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
MAX_TRIES = 2
RETRY_BACKOFF = 1.0
socket.setdefaulttimeout(10)

POS_CUTOFF, NEG_CUTOFF = 0.05, -0.05
_analyzer = SentimentIntensityAnalyzer()

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

TOPIC_KEYWORDS = {
    "Politics": ["election", "parliament", "minister", "president", "senate",
                 "congress", "government", "vote", "policy", "diplomat", "modi",
                 "trump", "biden", "putin", "campaign", "lawmaker", "summit"],
    "Conflict & War": ["war", "ukraine", "gaza", "israel", "hamas", "strike",
                       "military", "troops", "attack", "missile", "ceasefire",
                       "conflict", "killed", "rebel", "airstrike", "hostage"],
    "Business": ["economy", "market", "stocks", "inflation", "trade", "bank",
                 "rupee", "dollar", "gdp", "company", "ipo", "profit", "tariff",
                 "oil price", "investor", "shares", "revenue"],
    "Technology": ["artificial intelligence", "tech", "software", "chip",
                   "google", "apple", "microsoft", "openai", "iphone",
                   "cyber", "robot", "semiconductor", "app store"],
    "Sports": ["cricket", "football", "soccer", "world cup", "olympic", "match",
               "tournament", "ipl", "fifa", "tennis", "nba", "champion",
               "league", "wicket", "goal"],
    "Health": ["health", "covid", "virus", "vaccine", "hospital", "disease",
               "outbreak", "mental health", "cancer", "medical", "flu"],
    "Science & Environment": ["climate", "space", "nasa", "weather", "flood",
                              "earthquake", "wildfire", "environment", "research",
                              "study", "emissions", "heatwave", "cyclone", "monsoon"],
    "Entertainment": ["film", "movie", "music", "actor", "celebrity", "bollywood",
                      "hollywood", "box office", "award", "concert", "festival"],
    "Crime & Justice": ["court", "police", "arrest", "murder", "trial", "verdict",
                        "fraud", "crime", "jail", "lawsuit", "probe"],
}
DEFAULT_TOPIC = "General"
_COMPILED = {
    topic: [re.compile(r"\b" + re.escape(k) + r"\b") for k in kws]
    for topic, kws in TOPIC_KEYWORDS.items()
}


def clean_text(value):
    if not value:
        return ""
    return _WS_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", value))).strip()


def label_for(c):
    return "positive" if c >= POS_CUTOFF else "negative" if c <= NEG_CUTOFF else "neutral"


def classify(text):
    t = (text or "").lower()
    best, best_hits = DEFAULT_TOPIC, 0
    for topic, pats in _COMPILED.items():
        hits = sum(1 for p in pats if p.search(t))
        if hits > best_hits:
            best, best_hits = topic, hits
    return best


def _published_iso(entry):
    tm = entry.get("published_parsed") or entry.get("updated_parsed")
    if not tm:
        return None
    return datetime.fromtimestamp(calendar.timegm(tm), tz=timezone.utc).isoformat()


def _fetch(name, url):
    report = {"name": name, "ok": False, "count": 0, "error": None}
    for attempt in range(1, MAX_TRIES + 1):
        parsed = None
        try:
            parsed = feedparser.parse(url, agent=USER_AGENT)
        except Exception as exc:  # RemoteDisconnected, socket timeout, etc.
            report["error"] = f"{type(exc).__name__}: {exc}"

        if parsed is not None and parsed.entries:
            rows = []
            for e in parsed.entries:
                title = clean_text(e.get("title"))
                if not title:
                    continue
                c = _analyzer.polarity_scores(title)["compound"]
                rows.append({
                    "source": name,
                    "title": title,
                    "link": e.get("link", ""),
                    "published": _published_iso(e),
                    "compound": round(c, 4),
                    "label": label_for(c),
                    "topic": classify(title),
                })
            report.update(ok=True, count=len(rows), error=None)
            return rows, report
        if parsed is not None and not parsed.entries:
            report["error"] = str(parsed.get("bozo_exception", "no entries"))
        if attempt < MAX_TRIES:
            time.sleep(RETRY_BACKOFF * attempt)
    return [], report


def generate_payload():
    """Fetch all feeds, score + tag, dedupe, and return the JSON-ready dict the
    frontend consumes. Never raises -- dead feeds show up in the feeds report."""
    headlines, reports, seen = [], [], set()
    for feed in FEEDS:
        rows, report = _fetch(feed["name"], feed["url"])
        for r in rows:
            key = (r["source"], r["title"])
            if key in seen:
                continue
            seen.add(key)
            headlines.append(r)
        reports.append(report)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total": len(headlines),
        "feeds": reports,
        "headlines": headlines,
    }
