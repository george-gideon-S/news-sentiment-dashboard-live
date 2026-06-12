"""News Sentiment Dashboard -- Streamlit front end.

    streamlit run app.py

Reads the cache written by pipeline.py and draws it. The only thing that triggers
a live scrape is the 'Refresh feeds' button in the sidebar, and that clears the
cache so the fresh pull shows up immediately. Everything else is just reading and
slicing a DataFrame, which is why the UI stays instant.
"""
from __future__ import annotations

import plotly.express as px
import streamlit as st

import pipeline

st.set_page_config(page_title="News Sentiment Dashboard", page_icon=":newspaper:",
                   layout="wide")

SENT_COLORS = {"positive": "#2ca02c", "neutral": "#9aa0a6", "negative": "#d62728"}
SENT_ORDER = ["positive", "neutral", "negative"]
SENT_EMOJI = {"positive": "🟢", "neutral": "⚪", "negative": "🔴"}


@st.cache_data(ttl=900, show_spinner=False)
def load_data():
    """Cached read of the last pipeline run. The cache is what stops Streamlit
    from re-reading the CSV on every single widget interaction (it reruns the
    whole script top-to-bottom each time -- easy to forget, murder on perf)."""
    df, meta = pipeline.load_cache()
    if df.empty:
        # Cold start: nothing cached yet -> do one live run so the page isn't blank.
        df, meta = pipeline.run()
    return df, meta


def refresh():
    with st.spinner("Scraping feeds live…"):
        pipeline.run()
    load_data.clear()


# ----- Sidebar: controls + filters ---------------------------------------
st.sidebar.title("📰 Controls")
if st.sidebar.button("🔄 Refresh feeds (live scrape)", width="stretch"):
    refresh()
    st.rerun()

df, meta = load_data()

if df.empty:
    st.title("📰 News Sentiment Dashboard")
    st.warning("No headlines yet — the feeds couldn't be reached and there's no "
               "cache on disk. Hit **Refresh feeds** once you've got a connection.")
    st.stop()

sources = sorted(df["source"].unique())
topics = sorted(df["topic"].unique())
sel_sources = st.sidebar.multiselect("Sources", sources, default=sources)
sel_topics = st.sidebar.multiselect("Topics", topics, default=topics)
sel_sent = st.sidebar.multiselect("Sentiment", SENT_ORDER, default=SENT_ORDER)
query = st.sidebar.text_input("Search headlines")

mask = (df["source"].isin(sel_sources)
        & df["topic"].isin(sel_topics)
        & df["sent_label"].isin(sel_sent))
if query:
    mask &= df["title"].str.contains(query, case=False, na=False)
view = df[mask]

st.sidebar.divider()
st.sidebar.caption("Feed status (last run)")
for r in meta.get("feeds", []):
    icon = "🟢" if r.get("ok") else "🔴"
    st.sidebar.caption(f"{icon} {r['name']} — {r.get('count', 0)} items")

# ----- Header + KPIs -----------------------------------------------------
st.title("📰 News Sentiment Dashboard")
st.caption(f"Last updated: {meta.get('last_run', '—')}  •  "
           f"{len(df)} headlines across {df['source'].nunique()} sources  •  "
           "sentiment via VADER")

if view.empty:
    st.info("No headlines match these filters.")
    st.stop()

total = len(view)
counts = view["sent_label"].value_counts()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Headlines", total)
c2.metric("🟢 Positive", f"{counts.get('positive', 0)}",
          f"{counts.get('positive', 0) / total:.0%}")
c3.metric("⚪ Neutral", f"{counts.get('neutral', 0)}",
          f"{counts.get('neutral', 0) / total:.0%}", delta_color="off")
c4.metric("🔴 Negative", f"{counts.get('negative', 0)}",
          f"-{counts.get('negative', 0) / total:.0%}")

st.divider()

# ----- Charts ------------------------------------------------------------
left, right = st.columns([3, 2])

with left:
    st.subheader("Which topics lean positive or negative?")
    topic_sent = (view.groupby("topic")["sent_compound"]
                  .agg(avg="mean", n="count").reset_index()
                  .sort_values("avg"))
    fig = px.bar(topic_sent, x="avg", y="topic", orientation="h",
                 color="avg", range_color=[-1, 1],
                 color_continuous_scale=["#d62728", "#9aa0a6", "#2ca02c"],
                 labels={"avg": "Average sentiment (compound)", "topic": ""},
                 hover_data={"n": True, "avg": ":.3f"})
    fig.add_vline(x=0, line_dash="dash", line_color="#888")
    fig.update_layout(coloraxis_showscale=False, height=420,
                      margin=dict(l=0, r=10, t=10, b=0))
    st.plotly_chart(fig, width="stretch")

with right:
    st.subheader("Overall mix")
    mix = (view["sent_label"].value_counts()
           .reindex(SENT_ORDER).fillna(0).reset_index())
    mix.columns = ["sentiment", "count"]
    fig2 = px.pie(mix, names="sentiment", values="count", hole=0.55,
                  color="sentiment", color_discrete_map=SENT_COLORS)
    fig2.update_traces(textinfo="percent+label")
    fig2.update_layout(height=420, margin=dict(l=0, r=0, t=10, b=0),
                       showlegend=False)
    st.plotly_chart(fig2, width="stretch")

st.subheader("Sentiment by source")
src = view.groupby(["source", "sent_label"]).size().reset_index(name="count")
fig3 = px.bar(src, x="source", y="count", color="sent_label",
              color_discrete_map=SENT_COLORS,
              category_orders={"sent_label": SENT_ORDER},
              labels={"count": "Headlines", "source": "", "sent_label": "Sentiment"})
fig3.update_layout(height=360, barmode="stack",
                   margin=dict(l=0, r=0, t=10, b=0))
st.plotly_chart(fig3, width="stretch")

# ----- Headlines table ---------------------------------------------------
st.subheader("Headlines (most negative first)")
show = view.sort_values("sent_compound").copy()
show["S"] = show["sent_label"].map(SENT_EMOJI)
show = show[["S", "source", "topic", "sent_compound", "title", "link", "published"]]
st.dataframe(
    show, width="stretch", hide_index=True, height=460,
    column_config={
        "S": st.column_config.TextColumn("", width="small"),
        "source": st.column_config.TextColumn("Source"),
        "topic": st.column_config.TextColumn("Topic"),
        "sent_compound": st.column_config.NumberColumn("Score", format="%.2f"),
        "title": st.column_config.TextColumn("Headline", width="large"),
        "link": st.column_config.LinkColumn("Link", display_text="open ↗"),
        "published": st.column_config.DatetimeColumn("Published", format="MMM D, HH:mm"),
    },
)

st.caption("Sentiment: VADER (lexicon-based) on headline text, bucketed at "
           "±0.05 compound. Topics: keyword matching — crude but fully "
           "explainable. Sources: BBC · Times of India · Al Jazeera · The Hindu · NPR.")
