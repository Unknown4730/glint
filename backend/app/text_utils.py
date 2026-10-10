"""Text clean-up and small regular-expression helpers.

These functions are pure: they take a string and return a string or a list.
That makes them easy to unit test and easy to explain.

Important: the pattern helpers are *regex* matches, not semantic understanding.
They may produce false positives, so the UI presents them as "detected
patterns" and never as verified facts.

Concepts demonstrated: regular expressions, string manipulation, loops,
dictionaries and de-duplication while preserving order.
"""

from __future__ import annotations

import re
from typing import Dict, List

# Cap the number of matches so a huge document cannot produce a huge payload.
MAX_MATCHES_PER_TYPE = 40

# ---------------------------------------------------------------------------
# Regular expressions
# ---------------------------------------------------------------------------

EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)

# 2026-10-10 / 2026/10/10
DATE_ISO_PATTERN = re.compile(r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b")
# 10/12/2026 or 10.12.2026 or 10/12/26 (day and month order depends on locale)
DATE_DMY_PATTERN = re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](\d{2,4})\b")
# 12 March 2026 / March 12, 2026 / 12 Mar 26
MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|"
    "November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
)
DATE_TEXTUAL_PATTERN = re.compile(
    rf"\b(?:({MONTHS})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{2,4}})"
    rf"|(\d{{1,2}})(?:st|nd|rd|th)?\s+({MONTHS})\.?,?\s+(\d{{2,4}}))\b",
    re.IGNORECASE,
)

CURRENCY_SYMBOLS = r"$\u20ac\u00a3\u00a5\u20b9"  # $ euro pound yen rupee
CURRENCY_PATTERN = re.compile(
    rf"(?:[{CURRENCY_SYMBOLS}]\s?\d{{1,3}}(?:[,\s]\d{{3}})*(?:\.\d{{1,2}})?"
    rf"|[{CURRENCY_SYMBOLS}]\s?\d+(?:\.\d{{1,2}})?"
    rf"|\b(?:USD|EUR|GBP|INR|JPY|AUD|CAD)\s?\d{{1,3}}(?:[,]\d{{3}})*(?:\.\d{{1,2}})?\b)"
)

# Obvious OCR/formatting noise.
MULTI_BLANK_LINES = re.compile(r"\n{3,}")
TRAILING_SPACES = re.compile(r"[ \t]+\n")
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


# ---------------------------------------------------------------------------
# Clean-up
# ---------------------------------------------------------------------------

def normalize_text(lines: List[str]) -> str:
    """Join recognized lines into one clean, readable block of text.

    The goal is readability, *not* rewriting: line endings are normalized,
    trailing spaces are removed and runs of blank lines are collapsed. The
    recognized words themselves are never changed.
    """
    if not lines:
        return ""

    cleaned: List[str] = []
    for line in lines:
        if line is None:
            continue
        # RapidOCR returns plain strings; be defensive anyway.
        text = str(line).replace("\r\n", "\n").replace("\r", "\n")
        text = CONTROL_CHARS.sub("", text)
        for part in text.split("\n"):
            cleaned.append(part.strip())

    joined = "\n".join(cleaned)
    joined = TRAILING_SPACES.sub("\n", joined)
    joined = MULTI_BLANK_LINES.sub("\n\n", joined)
    return joined.strip()


def count_lines(text: str) -> int:
    """Number of non-empty lines in a block of text."""
    if not text:
        return 0
    return sum(1 for line in text.split("\n") if line.strip())


# ---------------------------------------------------------------------------
# Pattern extraction
# ---------------------------------------------------------------------------

def _unique(values: List[str]) -> List[str]:
    """Remove duplicates while keeping the original order, then cap the list."""
    seen = set()
    result: List[str] = []
    for value in values:
        key = value.strip()
        if not key or key.lower() in seen:
            continue
        seen.add(key.lower())
        result.append(key)
        if len(result) >= MAX_MATCHES_PER_TYPE:
            break
    return result


def _plausible_date(year: int, month: int, day: int) -> bool:
    """Cheap sanity check so that "99/99/9999" is not reported as a date."""
    if not 1 <= month <= 12:
        return False
    if not 1 <= day <= 31:
        return False
    if year < 100:
        year += 2000 if year < 70 else 1900
    return 1600 <= year <= 2200


def extract_emails(text: str) -> List[str]:
    """Return e-mail addresses found in the text."""
    if not text:
        return []
    return _unique(EMAIL_PATTERN.findall(text))


def extract_dates(text: str) -> List[str]:
    """Return date-like strings found in the text (original formatting kept)."""
    if not text:
        return []

    found: List[str] = []

    for match in DATE_ISO_PATTERN.finditer(text):
        year, month, day = (int(group) for group in match.groups())
        if _plausible_date(year, month, day):
            found.append(match.group(0))

    for match in DATE_DMY_PATTERN.finditer(text):
        first, second, year = (int(group) for group in match.groups())
        # Accept either day/month or month/day ordering.
        if _plausible_date(year, first, second) or _plausible_date(
            year, second, first
        ):
            found.append(match.group(0))

    for match in DATE_TEXTUAL_PATTERN.finditer(text):
        groups = match.groups()
        if groups[0]:  # "March 12, 2026"
            year = int(groups[2])
        else:  # "12 March 2026"
            year = int(groups[5])
        if 1600 <= (year + (2000 if year < 70 else 1900) if year < 100 else year) <= 2200:
            found.append(match.group(0))

    return _unique(found)


def extract_currency(text: str) -> List[str]:
    """Return currency amounts such as $1,250.75 or EUR 990."""
    if not text:
        return []
    matches = [match.group(0).strip() for match in CURRENCY_PATTERN.finditer(text)]
    return _unique(matches)


def extract_patterns(text: str) -> Dict[str, List[str]]:
    """Run every pattern extractor and return a small dictionary of results."""
    return {
        "emails": extract_emails(text),
        "dates": extract_dates(text),
        "currency": extract_currency(text),
    }


def pattern_total(patterns: Dict[str, List[str]]) -> int:
    """How many matches were found across all pattern types."""
    return sum(len(values) for values in patterns.values())
