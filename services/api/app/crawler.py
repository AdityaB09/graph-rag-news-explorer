# services/api/app/crawler.py
#working implementation
from __future__ import annotations

import os
import re
import urllib.parse
from typing import Any, Dict, List, Tuple, Optional

import requests
import feedparser

# -------------------- config knobs --------------------
FETCH_UA = os.getenv(
    "FETCH_UA",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
)
DEFAULT_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "20"))
MIN_CONTENT_LEN = int(os.getenv("MIN_CONTENT_LEN", "300"))
MAX_ITEMS_CAP = int(os.getenv("MAX_ITEMS_CAP", "60"))

_DEFAULT_HTML_HEADERS = {
    "User-Agent": FETCH_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_DEFAULT_RSS_HEADERS = {
    "User-Agent": FETCH_UA,
    "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
}


# -------------------- small utils --------------------
def _clean(s: Optional[str]) -> str:
    s = s or ""
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _http_get(url: str, rss: bool = False) -> requests.Response:
    headers = dict(_DEFAULT_RSS_HEADERS if rss else _DEFAULT_HTML_HEADERS)
    r = requests.get(
        url,
        headers=headers,
        timeout=DEFAULT_TIMEOUT,
        allow_redirects=True,
    )
    r.raise_for_status()
    return r


def _extract_text(html: str) -> str:
    """
    Best-effort text extraction:
    - use trafilatura if present (robust)
    - otherwise, a minimal fallback that strips tags crudely
    """
    try:
        import trafilatura  # type: ignore
        txt = trafilatura.extract(html) or ""
        return _clean(txt)
    except Exception:
        pass

    # ultra-minimal fallback: remove tags & collapse whitespace
    # (kept intentionally simple/robust)
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)  # strip tags
    text = _clean(text)
    return text


# -------------------- RSS parsing --------------------
def _parse_rss(raw_or_url: Any) -> List[Dict[str, Any]]:
    """
    Accepts raw bytes OR a URL; feedparser can fetch URLs itself.
    Returns a uniform list of {url,title,summary,published} items.
    """
    feed = feedparser.parse(raw_or_url)
    items: List[Dict[str, Any]] = []
    for e in feed.entries or []:
        link = e.get("link") or e.get("id")
        title = e.get("title") or (link or "")
        if not link:
            continue
        # feedparser often exposes multiple summary-ish fields
        summary = e.get("summary") or e.get("description") or ""
        published = (
            e.get("published")
            or e.get("updated")
            or e.get("pubDate")
            or e.get("issued")
        )
        items.append(
            {
                "url": _clean(link),
                "title": _clean(title),
                "summary": _clean(summary),
                "published": _clean(published),
            }
        )
    return items


def fetch_rss(rss_url: str) -> Tuple[List[Dict[str, Any]], str]:
    """
    Returns (items, diag).
    Try requests+parse first; if that fails, let feedparser fetch the URL directly.
    """
    try:
        r = _http_get(rss_url, rss=True)
        items = _parse_rss(r.content)
        return items, f"requests+parse ok [{len(items)}]"
    except Exception as ex:
        print(f"[crawler] fetch_rss via requests FAILED {rss_url}: {ex}")

    try:
        items = _parse_rss(rss_url)  # feedparser fetch
        return items, f"feedparser-fetch ok [{len(items)}]"
    except Exception as ex:
        print(f"[crawler] feedparser-fetch FAILED {rss_url}: {ex}")
        return [], f"both failed: {type(ex).__name__}"


# -------------------- news source builders --------------------
def _google_news_rss(topic: str) -> str:
    q = urllib.parse.quote_plus(topic.strip())
    # Google News RSS for search
    return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


def _bing_news_rss(topic: str) -> str:
    q = urllib.parse.quote_plus(topic.strip())
    # Bing News RSS – often more tolerant behind proxies/containers
    return f"https://www.bing.com/news/search?q={q}&setlang=en&format=RSS"


# -------------------- topic flow --------------------
def fetch_topic(topic: str, max_items: int = 30) -> Dict[str, Any]:
    """
    Fetch a topic from one or more news RSS sources with diagnostics.
    Returns:
      {
        "source_used": "google"|"bing"|None,
        "attempts": [{"source":"google","count":N,"diag": "..."}...],
        "items": [{"url", "title", "summary", "published"}, ...]   # sliced to max_items
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
            limit = min(int(max_items or 30), MAX_ITEMS_CAP)
            return {
                "source_used": name,
                "attempts": attempts,
                "items": items[:limit],
            }

    print(f"[crawler] fetch_topic: 0 items for '{topic}' after {len(attempts)} attempts")
    return {"source_used": None, "attempts": attempts, "items": []}


# -------------------- article hydration --------------------
def fetch_url(url: str) -> Dict[str, Any]:
    """
    Fetch a single article URL and extract text.
    Returns: {title, text, published_at} (title best-effort; you can enhance with your own extractor)
    """
    try:
        r = _http_get(url, rss=False)
        if r.status_code == 200 and "text/html" in r.headers.get("content-type", ""):
            html = r.text
            text = _extract_text(html)
            # Rough title guess if we don’t parse <title> specifically:
            title = url
            m = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
            if m:
                title = _clean(m.group(1))
            return {"title": title or url, "text": text, "published_at": None}
    except Exception as ex:
        print(f"[crawler] fetch_url FAILED {url}: {ex}")

    # fallback: minimal entry (no text)
    return {"title": url, "text": "", "published_at": None}


def hydrate_items_with_text(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    For each RSS item, try to fetch & extract full article text.
    If fetch/extract fails or is short, fall back to the feed summary/description.
    Returns a dict with 'saved' (ready-to-persist) and a summary line.
    """
    seen = set()
    saved: List[Dict[str, Any]] = []
    n_feed = 0
    n_ok = 0
    n_block = 0
    n_short = 0
    n_dup = 0
    n_saved = 0

    for item in items:
        n_feed += 1
        url = item.get("url") or ""
        if not url or url in seen:
            n_dup += 1
            continue
        seen.add(url)

        # 1) try full article
        text = ""
        title = item.get("title") or url
        try:
            r = _http_get(url, rss=False)
            if r.status_code == 200 and "text/html" in r.headers.get("content-type", ""):
                html = r.text
                text = _extract_text(html)
                # improve title if available
                m = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
                if m:
                    t2 = _clean(m.group(1))
                    if t2:
                        title = t2
                n_ok += 1
            else:
                n_block += 1
        except Exception:
            n_block += 1

        # 2) fallback to feed summary if article text is too short
        if len(text) < MIN_CONTENT_LEN:
            feed_txt = _clean(item.get("summary") or "")
            if feed_txt and len(feed_txt) >= 100:
                text = feed_txt
            else:
                n_short += 1

        if not text:
            # truly nothing to persist
            continue

        saved.append(
            {
                "title": title or "(untitled)",
                "url": url,
                "text": text,
                "published_at": item.get("published"),
                "source": item.get("source") or "topic-rss",
            }
        )
        n_saved += 1

    diag = (
        f"[ingest-summary] feed_items={n_feed} fetched_ok={n_ok} "
        f"blocked={n_block} short={n_short} dup={n_dup} saved={n_saved}"
    )
    print(diag, flush=True)
    return {"saved": saved, "diag": diag}
