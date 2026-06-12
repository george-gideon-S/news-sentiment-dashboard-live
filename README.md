# News Sentiment Dashboard

Scrapes headlines from five news RSS feeds, scores each headline's sentiment with
VADER, tags it with a topic, and serves a live Streamlit dashboard showing which
topics and sources lean positive, negative or neutral.

**Feeds:** BBC · Times of India · Al Jazeera · The Hindu · NPR

## How it's wired

```
feeds.py      list of (name, url) — the only place feeds are defined
scrape.py     fetch + clean every feed into a tidy DataFrame (defensive: a dead
              feed is data, not a crash)
sentiment.py  VADER compound score + positive/neutral/negative label per headline
topics.py     keyword-based topic tagging (deliberately simple — see note below)
pipeline.py   fetch -> sentiment -> topics -> write data/headlines.csv + run_meta.json
app.py        Streamlit dashboard that reads the cache and draws it
```

The producer (`pipeline.py`) writes the cache; the dashboard only ever reads it.
That separation is what keeps the UI instant and stops it hammering the feeds on
every filter click. In production you'd run `pipeline.py` on a cron and leave the
dashboard pointed at the cache.

## Run it

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt

# one scrape to populate the cache
.venv/Scripts/python.exe pipeline.py

# launch the dashboard  ->  http://localhost:8501
.venv/Scripts/python.exe -m streamlit run app.py
```

The **Refresh feeds** button in the sidebar triggers a live re-scrape on demand.

### If pip/SSL fails on a locked-down box

If `pip install` dies with `CERTIFICATE_VERIFY_FAILED`, the machine's CA trust
store is stale. Add trusted hosts:

```bash
.venv/Scripts/python.exe -m pip install --trusted-host pypi.org \
    --trusted-host files.pythonhosted.org -r requirements.txt
```

## Choices & cut corners (on purpose)

- **VADER, not a trained model.** Headlines are short and punchy — exactly VADER's
  wheelhouse. Zero training, instant, explainable. A custom classifier would be a
  week of work to do worse on day one.
- **Keyword topics, not topic modelling.** The topic tagger in `topics.py` is a
  keyword map. It's crude, but it's transparent and anyone can tune it by editing
  a list. When keywords start embarrassing the dashboard, *that's* the cue to swap
  in zero-shot / BERTopic — not before.
- **Sentiment is scored on the headline title only.** That's the "headline
  sentiment" everyone actually means; summaries are teaser text that muddies it.
- **One slow feed can't hang the run** — global socket timeout, and every feed
  fetch is wrapped so a failure is logged and skipped, never fatal.
