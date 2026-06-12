"""Dirt-simple topic tagging by keyword.

Full disclosure: this is the corner I'm cutting, and I'll say it out loud. Real
topic modelling (zero-shot classification, BERTopic, an LLM call per headline) is
overkill for a v1 dashboard and a pain to keep running. A keyword map gets me 80%
of the way there, it's fully explainable -- "why is this Sports? because it said
'World Cup'" -- and anyone can tune it by editing a list. When the keywords start
embarrassing me, *that's* the signal to reach for a model. Not before.
"""
from __future__ import annotations

import re

import pandas as pd

# Classification picks the bucket with the most keyword hits. Keep everything
# lowercase. Multi-word phrases are fine -- they're matched with word boundaries.
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

# Pre-compile boundary-anchored matchers so "ai"-in-"said" and the like never
# false-trigger, and multi-word phrases still work.
_COMPILED = {
    topic: [re.compile(r"\b" + re.escape(k) + r"\b") for k in kws]
    for topic, kws in TOPIC_KEYWORDS.items()
}


def classify(text: str) -> str:
    t = (text or "").lower()
    best, best_hits = DEFAULT_TOPIC, 0
    for topic, patterns in _COMPILED.items():
        hits = sum(1 for p in patterns if p.search(t))
        if hits > best_hits:
            best, best_hits = topic, hits
    return best


def add_topics(df: pd.DataFrame, text_col: str = "title") -> pd.DataFrame:
    if df.empty:
        df["topic"] = pd.Series(dtype="object")
        return df
    df = df.copy()
    df["topic"] = df[text_col].apply(classify)
    return df
