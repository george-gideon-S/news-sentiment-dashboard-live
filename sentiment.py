"""Sentiment scoring with VADER.

Why VADER and not something I'd train: headlines are short, punchy and almost
social-media-ish in tone, which is exactly what VADER was tuned for. It's
lexicon + rules, needs zero training data, and spits out a single 'compound'
score in [-1, 1] that's trivial to bucket. Training a classifier for news
headlines is a week of work to do *worse* on day one. Not for v1.
"""
from __future__ import annotations

import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer = SentimentIntensityAnalyzer()

# VADER's own recommended thresholds for the compound score.
POS_CUTOFF = 0.05
NEG_CUTOFF = -0.05

_SCORE_COLS = ["sent_compound", "sent_pos", "sent_neu", "sent_neg"]


def label_for(compound: float) -> str:
    if compound >= POS_CUTOFF:
        return "positive"
    if compound <= NEG_CUTOFF:
        return "negative"
    return "neutral"


def score_text(text: str) -> dict:
    s = _analyzer.polarity_scores(text or "")
    return {
        "sent_compound": s["compound"],
        "sent_pos": s["pos"],
        "sent_neu": s["neu"],
        "sent_neg": s["neg"],
        "sent_label": label_for(s["compound"]),
    }


def add_sentiment(df: pd.DataFrame, text_col: str = "title") -> pd.DataFrame:
    """Score the headline text and glue the columns on.

    Scoring the *title* is deliberate -- that's the 'headline sentiment' everyone
    actually means when they say this. The summary is usually a teaser sentence
    that just muddies the signal.
    """
    if df.empty:
        for col in _SCORE_COLS:
            df[col] = pd.Series(dtype="float64")
        df["sent_label"] = pd.Series(dtype="object")
        return df
    scores = df[text_col].apply(score_text).apply(pd.Series)
    return pd.concat([df, scores], axis=1)
