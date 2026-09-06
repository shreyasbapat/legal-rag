"""Extracts case-law citation strings from judgment text.

Covers the three reporter formats that dominate Indian case law:
  - AIR:  "AIR 1973 SC 1461"
  - SCC:  "(1973) 4 SCC 225"   or   "1973 4 SCC 225"
  - SCR:  "1973 SCR (1) 1"

This is deliberately a string-level extraction step. Resolving a raw string
to a specific Judgment row (matching against Judgment.citation) and
classifying how it's being used (followed/distinguished/overruled) are
separate concerns, handled in the ingestion pipeline and left for a later
LLM-assisted pass, respectively.
"""

from __future__ import annotations

import re

_AIR = r"AIR\s+\d{4}\s+[A-Z]{2,10}\s+\d+"
_SCC = r"\(?\d{4}\)?\s+\d{1,2}\s+SCC\s+\d+"
_SCR = r"\d{4}\s+SCR\s*\(?\d{1,3}\)?\s+\d+"

_CITATION_RE = re.compile(f"(?:{_AIR})|(?:{_SCC})|(?:{_SCR})")


def extract_citations(text: str) -> list[str]:
    """Return citation strings found in ``text``, deduplicated, in order of first appearance."""
    seen: set[str] = set()
    ordered: list[str] = []
    for match in _CITATION_RE.finditer(text):
        normalized = " ".join(match.group(0).split())
        if normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)
    return ordered
