from typing import Optional, Dict, Any
import requests
from .config import FETCH_UA

_DEFAULT_HEADERS = {
    "User-Agent": FETCH_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

def get(url: str, headers: Optional[Dict[str, str]] = None, **kw: Any) -> requests.Response:
    hd = dict(_DEFAULT_HEADERS)
    if headers:
        hd.update(headers)
    kw.setdefault("timeout", 20)
    kw.setdefault("allow_redirects", True)
    return requests.get(url, headers=hd, **kw)
