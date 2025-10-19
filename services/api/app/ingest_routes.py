# services/api/app/ingest_routes.py
import re
import time
from typing import Optional, List
from urllib.parse import urlencode

import feedparser
import requests
import trafilatura
import yake

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from dateutil import parser as dtparse

from .db import exec_sql

router = APIRouter(prefix="/ingest", tags=["ingest"])

# ---------- helpers ----------

def fetch_url(url: str, timeout=20):
    r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return r.text

def extract_text(html: str, url: Optional[str] = None):
    # trafilatura handles boilerplate removal nicely
    txt = trafilatura.extract(html, url=url)
    return txt or ""

def normalize_keywords(text: str, topk=12) -> List[tuple[str, float]]:
    # YAKE keyword extraction
    kw = yake.KeywordExtractor(lan="en", n=1, dedupLim=0.9, top=topk)
    pairs = kw.extract_keywords(text[:20000] if text else "")
    # returns list of (keyword, score) where lower score = more important
    # convert score to weight ~ (1/score)
    out = []
    for k, s in pairs:
        k = k.strip()
        if not k or len(k) < 3:
            continue
        # filter trivial tokens
        if re.fullmatch(r"[0-9\W_]+", k):
            continue
        out.append((k, float(1.0 / (s + 1e-6))))
    return out

def upsert_doc(url: str, title: str, summary: str, published_at, site: str):
    row = exec_sql("""
        INSERT INTO documents (url, title, summary, published_at, site)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (url) DO UPDATE
          SET title = EXCLUDED.title,
              summary = EXCLUDED.summary,
              published_at = COALESCE(EXCLUDED.published_at, documents.published_at),
              site = EXCLUDED.site
        RETURNING id;
    """, (url, title, summary, published_at, site), fetch=True)
    return row[0][0]

def upsert_keyword(name: str) -> int:
    row = exec_sql("""
        INSERT INTO keywords (name) VALUES (%s)
        ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
        RETURNING id;
    """, (name,), fetch=True)
    return row[0][0]

def link_doc_keyword(doc_id: int, kw_id: int, weight: float):
    exec_sql("""
        INSERT INTO doc_keyword (doc_id, keyword_id, weight)
        VALUES (%s, %s, %s)
        ON CONFLICT (doc_id, keyword_id) DO UPDATE
          SET weight = GREATEST(doc_keyword.weight, EXCLUDED.weight);
    """, (doc_id, kw_id, weight))

def google_news_rss_url(query: str, days: int = 14):
    # Google News RSS
    params = {"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"}
    return f"https://news.google.com/rss/search?{urlencode(params)}"

def parse_pubdate(val) -> Optional[str]:
    if not val:
        return None
    try:
        return dtparse.parse(str(val)).isoformat()
    except Exception:
        return None

def ingest_html_page(url: str):
    html = fetch_url(url)
    text = extract_text(html, url=url)
    return text, html

# ---------- request models ----------

class TopicReq(BaseModel):
    query: str
    days: Optional[int] = 14
    max_items: Optional[int] = 40

class RSSReq(BaseModel):
    url: HttpUrl
    days: Optional[int] = 14
    max_items: Optional[int] = 40

class URLReq(BaseModel):
    url: HttpUrl

# ---------- endpoints ----------

@router.post("/search")
def ingest_search(req: TopicReq):
    feed_url = google_news_rss_url(req.query, req.days or 14)
    return _ingest_rss(feed_url, req.max_items)

@router.post("/rss")
def ingest_rss(req: RSSReq):
    return _ingest_rss(str(req.url), req.max_items)

@router.post("/url")
def ingest_url(req: URLReq):
    try:
        url = str(req.url)
        text, html = ingest_html_page(url)
        title = re.search(r"<title>(.*?)</title>", html or "", re.I | re.S)
        title = (title.group(1) if title else url).strip()
        site = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
        doc_id = upsert_doc(url, title, text[:280], None, site)
        for k, w in normalize_keywords(text, topk=12):
            kw_id = upsert_keyword(k)
            link_doc_keyword(doc_id, kw_id, w)
        return {"ok": True, "status": "ingested", "url": url, "doc_id": doc_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---------- core ingest ----------

def _ingest_rss(feed_url: str, max_items: Optional[int] = 40):
    try:
        feed = feedparser.parse(feed_url)
        if feed.get("bozo") and feed.get("bozo_exception"):
            raise RuntimeError(str(feed["bozo_exception"]))
        count = 0
        for entry in feed.entries[: max_items or 40]:
            url = entry.get("link") or entry.get("id")
            if not url:
                continue
            title = (entry.get("title") or "").strip() or url
            summary = (entry.get("summary") or "").strip()
            published = parse_pubdate(entry.get("published") or entry.get("updated"))
            site = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]

            # download full page and extract clean text
            try:
                text, _ = ingest_html_page(url)
            except Exception:
                # fall back to the entry summary if page fails
                text = summary

            doc_id = upsert_doc(url, title, text[:280] or summary[:280], published, site)

            # extract keywords & make edges
            for k, w in normalize_keywords(text, topk=12):
                kw_id = upsert_keyword(k)
                link_doc_keyword(doc_id, kw_id, w)
                count += 1

        return {"ok": True, "status": "ingested", "feed": feed_url, "edges_created": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
