# services/api/app/crawler.py
from __future__ import annotations

import os
import urllib.parse
import requests
import feedparser

UA = "GraphRAG-News/1.1 (+http://localhost)"
DEFAULT_TIMEOUT = 15


def _http_get(url: str) -> bytes:
    r = requests.get(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
        },
        timeout=DEFAULT_TIMEOUT,
        allow_redirects=True,
    )
    r.raise_for_status()
    return r.content


def fetch_url(url: str) -> dict:
    # Minimal placeholder (you can wire in your readability/extractor here).
    return {"title": url, "text": "", "published_at": None}


def _parse_rss(raw_or_url) -> list[dict]:
    """
    Accepts either raw bytes OR a URL.
    feedparser can fetch URLs itself; this helps when requests gets blocked/redirected.
    """
    feed = feedparser.parse(raw_or_url)
    items: list[dict] = []
    for e in feed.entries or []:
        link = e.get("link") or e.get("id")
        title = e.get("title") or (link or "")
        if not link:
            continue
        items.append({"url": link, "title": title})
    return items


def fetch_rss(rss_url: str) -> tuple[list[dict], str]:
    """
    Returns (items, diag).
    Try requests+parse first; if that fails, let feedparser fetch the URL directly.
    """
    try:
        raw = _http_get(rss_url)
        items = _parse_rss(raw)
        return items, f"requests+parse ok [{len(items)}]"
    except Exception as ex:
        print(f"[crawler] fetch_rss via requests FAILED {rss_url}: {ex}")

    try:
        items = _parse_rss(rss_url)  # feedparser fetch
        return items, f"feedparser-fetch ok [{len(items)}]"
    except Exception as ex:
        print(f"[crawler] feedparser-fetch FAILED {rss_url}: {ex}")
        return [], f"both failed: {type(ex).__name__}"


def _google_news_rss(topic: str) -> str:
    q = urllib.parse.quote_plus(topic.strip())
    # Google News RSS for search
    return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


def _bing_news_rss(topic: str) -> str:
    q = urllib.parse.quote_plus(topic.strip())
    # Bing News RSS – often more tolerant behind proxies/containers
    return f"https://www.bing.com/news/search?q={q}&setlang=en&format=RSS"


def fetch_topic(topic: str) -> dict:
    """
    Robust topic fetcher with diagnostics.
    Returns:
      {
        "source_used": "google"|"bing"|None,
        "attempts": [{"source":"google","count":N,"diag": "..."}...],
        "items": [{"url":..., "title":...}, ...]
      }
    """
    forced = os.getenv("TOPIC_SOURCE", "").lower().strip()
    if forced == "google":
        sources = [("google", _google_news_rss(topic))]
    elif forced == "bing":
        sources = [("bing", _bing_news_rss(topic))]
    else:
        sources = [
            ("google", _google_news_rss(topic)),
            ("bing", _bing_news_rss(topic)),
        ]

    attempts = []
    for name, url in sources:
        print(f"[crawler] fetch_topic trying {name}: {url}")
        items, diag = fetch_rss(url)
        attempts.append({"source": name, "count": len(items), "diag": diag})
        print(f"[crawler] fetch_topic {name} -> {len(items)} items ({diag})")
        if items:
            return {"source_used": name, "attempts": attempts, "items": items}

    print(f"[crawler] fetch_topic: 0 items for '{topic}' after {len(attempts)} attempts")
    return {"source_used": None, "attempts": attempts, "items": []}
