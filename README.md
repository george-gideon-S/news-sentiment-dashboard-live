# News Sentiment Dashboard

Scrapes headlines from five news RSS feeds, scores each headline's sentiment with
**VADER**, tags it with a topic, and shows which topics and sources lean positive,
negative or neutral.

**Live (Vercel):** https://news-sentiment-dashboard-live.vercel.app
**Feeds:** BBC · Times of India · Al Jazeera · The Hindu · NPR
**Walkthrough notebook:** [`News_Sentiment_Dashboard.ipynb`](News_Sentiment_Dashboard.ipynb) — the entire project in one runnable, executed file (start here to understand it end-to-end)

---

## Two ways it runs

This repo ships the same dashboard in two forms:

| | Local — Streamlit | Hosted — Vercel |
|---|---|---|
| File | `app.py` | `index.html` + `data.json` |
| Data | live scrape on demand | real snapshot baked at deploy time |
| Refresh button | re-scrapes live | shows the saved snapshot (static host) |
| Best for | interactive analysis | a public URL anyone can open |

Streamlit is a stateful, always-on server — it can't run on Vercel's serverless
model. So the Vercel deployment is a **static page** (`index.html`) that reads a
committed `data.json` snapshot and renders it with Plotly.js. Same feeds, same
scoring, same charts.

## Project layout

```
# Shared pipeline
feeds.py            the five feeds (single source of truth for the Streamlit app)
scrape.py           fetch + clean every feed (defensive: a dead feed is data, not a crash)
sentiment.py        VADER compound score + positive/neutral/negative label
topics.py           keyword-based topic tagging (deliberately simple — see notes)
pipeline.py         scrape -> sentiment -> topics -> data/headlines.csv (+ run_meta.json)

# Local dashboard
app.py              Streamlit dashboard reading the pipeline cache

# Vercel deployment
index.html          static dashboard (Plotly.js) — reads data.json
core.py             lean self-contained scrape+score+tag engine (feedparser + VADER only)
build_data.py       regenerates data.json from a live scrape
data.json           committed snapshot the hosted page renders
api/refresh.py      serverless live-scrape endpoint (see "Live refresh" below)

requirements.txt              lean deps (feedparser, vaderSentiment) — core.py / api
requirements-streamlit.txt    full deps (+ pandas, streamlit, plotly) — app.py
```

## Run the Streamlit app locally

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-streamlit.txt

# one scrape to populate the cache
.venv/Scripts/python.exe pipeline.py

# launch  ->  http://localhost:8501
.venv/Scripts/python.exe -m streamlit run app.py
```

The **Refresh feeds** button re-scrapes live.

## Refresh the hosted snapshot

The Vercel page renders `data.json`. To update it with fresh headlines:

```bash
.venv/Scripts/python.exe build_data.py   # rewrites data.json from a live scrape
git commit -am "refresh data.json" && git push   # connected repo -> auto-redeploy
```

## Live refresh on Vercel (optional enhancement)

`api/refresh.py` is a ready-made serverless endpoint that does a live scrape and
returns JSON, which the dashboard's Refresh button calls. On 2026 Vercel, Python
runs as a single Fluid Compute app (one declared entrypoint) rather than per-file
`/api` functions, so wiring this on the hosted page means serving the static
assets and the API from one Python entrypoint. The current deploy is static for
simplicity; the endpoint is kept here for that next step (and works under
`vercel dev` locally).

## Choices & cut corners (on purpose)

- **VADER, not a trained model.** Headlines are short and punchy — VADER's
  wheelhouse. Zero training, instant, explainable. Its limit: lexicon scoring
  mis-reads things like *"Celebrated artist … dies"* as positive ("celebrated").
  Read the aggregates, not any single score.
- **Keyword topics, not topic modelling.** `topics.py` / `core.py` use a keyword
  map — crude but fully explainable, and ~half of headlines fall into "General".
  When that bugs you, swap in zero-shot / BERTopic behind the same interface.
- **Sentiment scores the headline title only** — that's the "headline sentiment"
  everyone means; summaries just muddy it.
- **One slow feed can't hang the run** — global socket timeout + per-feed retry
  (The Hindu reliably drops its first connection and answers on the second).

## Notes for locked-down machines

If `pip` / `git` fail with `CERTIFICATE_VERIFY_FAILED` / `unable to get local
issuer certificate`, the box's CA trust store is stale:

```bash
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements-streamlit.txt
git config http.sslBackend schannel   # Windows: use the OS cert store
```
