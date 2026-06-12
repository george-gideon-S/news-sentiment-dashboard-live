"""RSS feeds for the News Sentiment Dashboard.

Just a plain list of (name, url). Everything downstream is driven off this list,
so the rest of the pipeline doesn't care how many feeds there are or what order
they're in. Want another paper? Add a line here, done.
"""

FEEDS = [
    {"name": "BBC",            "url": "http://feeds.bbci.co.uk/news/rss.xml"},
    {"name": "Times of India", "url": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms"},
    {"name": "Al Jazeera",     "url": "https://www.aljazeera.com/xml/rss/all.xml"},
    {"name": "The Hindu",      "url": "https://www.thehindu.com/news/feeder/default.rss"},
    {"name": "NPR",            "url": "https://feeds.npr.org/1001/rss.xml"},
]
