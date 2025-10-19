# app/config.py

from typing import Final, Set

# Entities you never want to show in the graph (sources, boilerplate, etc.)
ENTITY_BLACKLIST: Final[Set[str]] = {
    "GOOGLE NEWS",
    "RSS", "HTTP", "HTTPS",
    "WWW",
}

# Prefer these entity types when scoring or selecting "about" relations.
# Typical spaCy / custom NER tags (ORG, PRODUCT, GPE for places used as org HQs)
PREFERRED_ENTITY_TYPES: Final[Set[str]] = {"ORG", "PRODUCT", "GPE"}

# Minimum shared-entity count to create a doc<->doc "related" edge
RELATED_DOC_MIN_SHARED: Final[int] = 3

# Cap graph size to keep UI snappy (you can raise if needed)
MAX_NODES: Final[int] = 250
MAX_EDGES: Final[int] = 1200
