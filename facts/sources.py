"""Where topics come from: free RSS feeds for news, the LLM for evergreen ideas."""
import calendar, html, re, time

FEEDS = {
    "ai_news": [
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        "https://news.mit.edu/rss/topic/artificial-intelligence2",
        "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
        "https://venturebeat.com/category/ai/feed/",
        "https://blog.google/technology/ai/rss/",
        "https://openai.com/news/rss.xml",
    ],
    "discovery": [
        "https://www.sciencedaily.com/rss/top/science.xml",
        "https://phys.org/rss-feed/",
        "https://www.nasa.gov/news-release/feed/",
        "https://www.livescience.com/feeds/all",
        "https://www.newscientist.com/feed/home/",
    ],
}

EVERGREEN_AREAS = {
    "explainer": ["space", "the human body", "animals", "physics", "chemistry",
                  "planet Earth", "the ocean", "the brain", "technology", "weather"],
    "fun": ["animals", "space", "the human body", "history of inventions", "food science",
            "the ocean", "insects", "language", "sleep", "colors and light"],
    "money": ["the psychology of money", "history of money", "famous market bubbles",
              "behavioral economics", "how banks and interest work", "the math of compounding"],
}


def _clean(s, n=600):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()[:n]


def fetch_items(kind, max_age_h=72, used_links=()):
    """Recent items from the kind's feeds that we haven't covered yet."""
    import feedparser
    now, items = time.time(), []
    for url in FEEDS[kind]:
        try:
            feed = feedparser.parse(url, agent="Mozilla/5.0 (shorts-bot)")
        except Exception:
            continue
        for e in feed.entries[:25]:
            link = e.get("link", "")
            if not link or link in used_links:
                continue
            ts = e.get("published_parsed") or e.get("updated_parsed")
            age_h = (now - calendar.timegm(ts)) / 3600 if ts else 24
            if age_h > max_age_h:
                continue
            items.append(dict(title=_clean(e.get("title", ""), 200),
                              summary=_clean(e.get("summary", "") or e.get("description", "")),
                              link=link, source=_clean(feed.feed.get("title", url), 60),
                              age_h=round(age_h, 1)))
    seen, out = set(), []
    for it in sorted(items, key=lambda x: x["age_h"]):
        k = it["title"].lower()[:60]
        if k not in seen and len(it["summary"]) > 80:
            seen.add(k)
            out.append(it)
    return out[:20]
