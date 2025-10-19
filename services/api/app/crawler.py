# services/api/app/crawler.py
from __future__ import annotations
from typing import List, Dict
from datetime import datetime
import feedparser
import trafilatura
import requests
from bs4 import BeautifulSoup

def _clean_html(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    # remove scripts/styles
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(separator=" ", strip=True)

def fetch_url(url: str) -> Dict:
    """Return {title, text, published_at} for a URL."""
    downloaded = trafilatura.fetch_url(url)
    text = trafilatura.extract(downloaded, include_comments=False) if downloaded else ""
    if not text:
        # fallback: requests + bs4
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            text = _clean_html(r.text)
        except Exception:
            text = ""

    title = ""
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        title = (soup.title.string or "").strip() if soup.title else url
    except Exception:
        title = url

    return {"title": title or url, "text": text or "", "published_at": datetime.utcnow()}

def fetch_rss(rss_url: str) -> List[Dict]:
    """Return list of {url, title, published_at} from RSS feed."""
    feed = feedparser.parse(rss_url)
    out = []
    for e in feed.entries[:50]:
        link = getattr(e, "link", None)
        title = getattr(e, "title", None)
        published = getattr(e, "published_parsed", None)
        dt = datetime(*published[:6]) if published else datetime.utcnow()
        if link:
            out.append({"url": link, "title": title or link, "published_at": dt})
    return out

def fetch_topic(topic: str) -> List[Dict]:
    # Use Google News RSS
    q = requests.utils.quote(topic)
    rss = f"https://news.google.com/rss/search?q={q}"
    return fetch_rss(rss)
