# services/api/app/nlp.py
from __future__ import annotations
import spacy
from sentence_transformers import SentenceTransformer

# load at module import so background tasks reuse models
_nlp = spacy.load("en_core_web_sm")
_emb = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

def extract_entities(text: str):
    doc = _nlp(text)
    ents = []
    for e in doc.ents:
        if e.label_ in ("ORG", "PERSON", "GPE"):
            ents.append((e.text.strip(), e.label_))
    # normalize dedup
    out = {}
    for name, etype in ents:
        out[name] = etype
    return [(k, v) for k, v in out.items()]

def embed(text: str):
    # MiniLM 384-dim
    vec = _emb.encode([text], normalize_embeddings=True)[0].tolist()
    return vec
