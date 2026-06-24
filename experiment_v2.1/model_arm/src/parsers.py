"""
Parsers for model responses. Each returns either a structured value or None.
A None signals a parse failure — runner handles retry.
"""

from __future__ import annotations

import re


COMP_OPTIONS = ("yes", "no", "unsure")


def parse_comprehension(raw: str) -> str | None:
    """Return one of 'Yes' / 'No' / 'Unsure', or None."""
    text = raw.strip().lower()
    # Strip surrounding punctuation / quotes
    text = re.sub(r"^[\W_]+|[\W_]+$", "", text)
    # Take first word
    first = text.split()[0] if text.split() else ""
    if first in COMP_OPTIONS:
        return first.capitalize()
    # Fall back: scan for any of the three words
    for opt in COMP_OPTIONS:
        if re.search(rf"\b{opt}\b", text):
            return opt.capitalize()
    return None


def parse_ordering(raw: str, expected_labels: list[str]) -> list[str] | None:
    """
    Return the labels in their order of appearance in `raw`, deduplicated,
    iff the set of found labels matches `expected_labels` exactly.
    Otherwise None.

    Labels are matched as standalone tokens (not as substrings of longer tokens),
    so passing ['1', '2', ..., '8'] won't match the '1' in '12'.
    """
    if not expected_labels:
        return None
    # Sort by length descending so multi-char labels match before shorter ones
    sorted_labels = sorted(expected_labels, key=len, reverse=True)
    pattern = (
        r"(?<![A-Za-z0-9])(" + "|".join(re.escape(lbl) for lbl in sorted_labels) + r")(?![A-Za-z0-9])"
    )
    found = re.findall(pattern, raw)
    seen, dedup = set(), []
    for tok in found:
        if tok not in seen:
            seen.add(tok)
            dedup.append(tok)
    if sorted(dedup) == sorted(expected_labels) and len(dedup) == len(expected_labels):
        return dedup
    return None


def parse_rating(raw: str, lo: int = 0, hi: int = 6) -> int | None:
    """Return the first integer in [lo, hi] found in the response, or None."""
    # Look for a standalone integer first
    m = re.search(r"(?<![\d.])(\d+)(?!\.\d)", raw)
    if m is None:
        return None
    val = int(m.group(1))
    if lo <= val <= hi:
        return val
    return None
