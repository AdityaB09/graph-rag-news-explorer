# app/topic.py
"""
Topic ingestion that avoids raw DSN/execute calls entirely.
Implementation:
- Fetch a small set of candidate articles for the topic (RSS-based baseline).
- Filter by simple keyword match.
- Upsert documents and (optionally) naive entities from the topic terms.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import List, Dict

import requests
from xml.etree import ElementTree as ET

from app.db import (
    SessionLocal,
    upsert_document,
    upsert_entity,
    link_doc_entity,
)

# A small, dependency-free RSS fetch (NYT World is a decent broad baseline).
# You can add more feeds if you like; topic keywords will filter them.
RSS_SOURCES = [
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
]

def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()

def _split_terms(topic: str) -> List[str]:
    # Simple keyword list for matching
    words = re.split(r"[^\w]+", topic.lower())
    return [w for w in words if w]

def _match_topic(title: str, topic_terms: List[str]) -> bool:
    t = (title or "").lower()
    return any(w in t for w in topic_terms)

def _parse_pubdate(text: str) -> datetime | None:
    # Try common formats; otherwise None (DB column is nullable)
    from email.utils import parsedate_to_datetime
    try:
        return parsedate_to_datetime(text)
    except Exception:
        return None

def _fetch_rss_items(feed_url: str) -> List[Dict]:
    """
    Return list of items: {title, link, published_at}
    """
    out: List[Dict] = []
    r = requests.get(feed_url, timeout=20)
    r.raise_for_status()
    x = ET.fromstring(r.content)

    # Works for RSS2.0 (item under channel). For Atom, you'd adapt.
    for item in x.findall("./channel/item"):
        title = _normalize((item.findtext("title") or ""))
        link = _normalize((item.findtext("link") or ""))
        pub = item.findtext("pubDate") or ""
        published_at = _parse_pubdate(pub)

        if not link:
            continue
        out.append({
            "title": title,
            "url": link,
            "published_at": published_at,
            "source": feed_url,
        })
    return out

def ingest_topic(topic: str) -> List[Dict]:
    """
    Fetch candidate news from a couple of RSS feeds, filter by topic keywords,
    and upsert into DB. Returns a list of {"doc_id", "title", "url", "published_at"}.
    """
    topic = _normalize(topic)
    if not topic:
        return []

    terms = _split_terms(topic)
    candidates: List[Dict] = []

    # 1) Pull from each feed
    for feed in RSS_SOURCES:
        try:
            items = _fetch_rss_items(feed)
            candidates.extend(items)
        except Exception as e:
            # Non-fatal; continue other feeds
            print(f"[topic] RSS fetch failed for {feed}: {e}")

    # 2) Filter by topic match
    matches = [it for it in candidates if _match_topic(it.get("title", ""), terms)]

    # 3) Upsert docs and annotate simple entities = the topic terms
    results: List[Dict] = []
    for it in matches:
        doc_id = upsert_document(
            url=it["url"],
            title=it.get("title"),
            source=it.get("source"),
            published_at=it.get("published_at"),
            text=None,            # leave text empty; your URL/RSS pipelines can fill it later
            text_content=None,
        )
        results.append({
            "doc_id": str(doc_id),
            "title": it.get("title"),
            "url": it.get("url"),
            "published_at": (
                it["published_at"].isoformat() if it.get("published_at") else None
            ),
        })

        # Optional: record naive "mentions" relations for each topic term as entities
        try:
            with SessionLocal() as s:
                for w in set(terms):
                    if not w:
                        continue
                    ent_id = upsert_entity(s, name=w, etype="topic")
                    # Use generic relation "mentions"
                    link_doc_entity(doc_id=doc_id, ent_id=ent_id, relation="mentions")
        except Exception as e:
            print(f"[topic] entity linking failed for {it.get('url')}: {e}")

    return results
