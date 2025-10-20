# services/api/app/nlp.py
from __future__ import annotations
import re
from typing import List, Tuple

# ---------- Lazy/optional model loading ----------
_SPACY = None
_STMODEL = None
_SPACY_ERR = None
_ST_ERR = None

def _ensure_spacy():
    global _SPACY, _SPACY_ERR
    if _SPACY is not None or _SPACY_ERR is not None:
        return
    try:
        import spacy  # type: ignore
        _SPACY = spacy.load("en_core_web_sm")
    except Exception as e:
        _SPACY_ERR = e

def _ensure_st():
    global _STMODEL, _ST_ERR
    if _STMODEL is not None or _ST_ERR is not None:
        return
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        _STMODEL = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    except Exception as e:
        _ST_ERR = e

# ---------- Heuristic fallback for NER ----------
_HINT_ORGS = {
    "Apple", "Foxconn", "Tata", "Tata Group", "Tata Electronics", "HCL", "HCLTech",
    "TSMC", "Samsung", "LG Electronics", "Eli Lilly", "Mahindra", "Embraer",
    "Nvidia", "Oppo", "Pegatron", "Wistron", "BEL", "BOE", "Sony", "Google",
    "Microsoft", "Amazon", "Meta",
}
_HINT_GEOS = {
    "India", "Taiwan", "China", "United States", "U.S.", "USA", "Japan",
    "Malaysia", "Vietnam", "South Korea", "France", "Germany",
}

_STOP = {
    "The","A","An","Of","For","And","In","On","At","By","From","To","With",
    "As","Or","But","Not","Is","Are","Was","Be","It","That","This","These",
    "Those","You","We","They"
}

# capitalized chunk (1–4 tokens) like "Tata Electronics"
_PROPN_CHUNK = re.compile(r"\b([A-Z][\w&\.-]+(?:\s+[A-Z][\w&\.-]+){0,3})\b")

def _normalize(s: str) -> str:
    import re as _re
    return _re.sub(r"\s+", " ", (s or "").strip())

def _looks_like_entity(phrase: str) -> bool:
    if not phrase or phrase in _STOP: return False
    if any(ch.isdigit() for ch in phrase): return False
    if len(phrase) < 3: return False
    return True

# ---------- Public API ----------
def extract_entities(text: str, title: str = "") -> List[Tuple[str, str]]:
    """
    Return list of (name, type) from title+text.
    Prefer spaCy if available; fall back to heuristics.
    Types: ORG / PERSON / GPE.
    """
    blob = _normalize(title) + "\n" + _normalize(text)

    # 1) spaCy first (if present)
    _ensure_spacy()
    if _SPACY:
        doc = _SPACY(blob)
        ents: list[tuple[str, str]] = [
            (e.text.strip(), e.label_)
            for e in doc.ents
            if e.label_ in ("ORG", "PERSON", "GPE")
        ]
        if ents:
            seen = set()
            out: list[tuple[str, str]] = []
            for name, etype in ents:
                key = (name.lower(), etype)
                if key in seen: continue
                seen.add(key)
                out.append((name, etype))
            return out[:40]

    # 2) Heuristic fallback (keyword hints + proper-noun chunks)
    low = blob.lower()
    out: list[tuple[str, str]] = []

    # keyword hints
    for kw in _HINT_ORGS:
        if kw.lower() in low:
            out.append((kw, "ORG"))
    for kw in _HINT_GEOS:
        if kw.lower() in low:
            out.append((kw, "GPE"))

    # proper-noun chunks
    for m in _PROPN_CHUNK.finditer(blob):
        phrase = _normalize(m.group(1))
        if not _looks_like_entity(phrase):
            continue
        etype = "GPE" if phrase in _HINT_GEOS else "ORG"
        out.append((phrase, etype))

    # dedup preserve order
    seen = set()
    uniq: list[tuple[str, str]] = []
    for name, etype in out:
        key = (name.lower(), etype)
        if key in seen: continue
        seen.add(key)
        uniq.append((name, etype))
    return uniq[:40]

def embed(text: str) -> List[float]:
    """
    Normalized embedding. If SentenceTransformer isn't available,
    return a deterministic 64-dim hashed BoW so the API never crashes.
    """
    _ensure_st()
    blob = _normalize(text)
    if _STMODEL:
        vec = _STMODEL.encode([blob], normalize_embeddings=True)[0].tolist()
        return vec

    # fallback
    import math
    dim = 64
    v = [0.0] * dim
    for tok in re.findall(r"\w+", blob.lower()):
        h = (hash(tok) % dim + dim) % dim
        v[h] += 1.0
    norm = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / norm for x in v]
