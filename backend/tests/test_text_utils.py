"""Tests for the regex helpers and the text clean-up (no OCR, no HTTP)."""

from __future__ import annotations

from app.text_utils import (
    count_lines,
    extract_currency,
    extract_dates,
    extract_emails,
    extract_patterns,
    normalize_text,
    pattern_total,
)


# ---------------------------------------------------------------------------
# normalize_text
# ---------------------------------------------------------------------------
def test_normalize_text_joins_lines_and_strips_spaces():
    lines = ["  Hello world  ", "Second line", "", "   "]
    assert normalize_text(lines) == "Hello world\nSecond line"


def test_normalize_text_converts_windows_line_endings():
    result = normalize_text(["First line\r\nSecond line"])
    assert result == "First line\nSecond line"
    assert "\r" not in result


def test_normalize_text_collapses_long_blank_runs():
    result = normalize_text(["A", "", "", "", "", "B"])
    assert result == "A\n\nB"


def test_normalize_text_removes_control_characters():
    result = normalize_text(["Clean\x00text\x1fhere"])
    assert result == "Cleantexthere"


def test_normalize_text_of_empty_input_is_empty_string():
    assert normalize_text([]) == ""


def test_normalize_text_never_changes_recognized_words():
    lines = ["Invoice  total :  $1,250.75"]
    # Only outer/trailing whitespace is touched, the words stay identical.
    assert normalize_text(lines) == "Invoice  total :  $1,250.75"


def test_count_lines_ignores_blank_lines():
    assert count_lines("a\n\nb\n   \nc") == 3
    assert count_lines("") == 0


# ---------------------------------------------------------------------------
# Emails
# ---------------------------------------------------------------------------
def test_extract_emails_finds_addresses():
    text = "Send to accounts@glint.app or support.team+eu@sub.glint.co.uk please"
    assert extract_emails(text) == [
        "accounts@glint.app",
        "support.team+eu@sub.glint.co.uk",
    ]


def test_extract_emails_removes_duplicates_case_insensitively():
    assert extract_emails("a@b.com and A@B.com") == ["a@b.com"]


def test_extract_emails_ignores_obvious_non_addresses():
    assert extract_emails("no at sign here, price is 5@x") == []


def test_extract_emails_handles_empty_text():
    assert extract_emails("") == []


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------
def test_extract_dates_iso_format():
    assert extract_dates("Issued 2026-10-10 today") == ["2026-10-10"]


def test_extract_dates_slash_and_dot_formats():
    found = extract_dates("Due 10/12/2026 or 10.12.2026")
    assert "10/12/2026" in found
    assert "10.12.2026" in found


def test_extract_dates_textual_formats():
    found = extract_dates("Signed 12 March 2026, updated March 3, 2026")
    assert "12 March 2026" in found
    assert "March 3, 2026" in found


def test_extract_dates_rejects_impossible_values():
    assert extract_dates("code 99/99/9999 is not a date") == []


def test_extract_dates_handles_two_digit_years():
    found = extract_dates("01/02/26")
    assert found == ["01/02/26"]


def test_extract_dates_empty_text():
    assert extract_dates("") == []


# ---------------------------------------------------------------------------
# Currency
# ---------------------------------------------------------------------------
def test_extract_currency_symbols():
    found = extract_currency("Total $1,250.75 plus 50 and EUR 990")
    assert "$1,250.75" in found
    assert "$50" in found or "50" not in found
    assert "EUR 990" in found


def test_extract_currency_euro_and_pound():
    found = extract_currency("Paid \u20ac2.499,00 and \u00a399.00")
    assert any("\u20ac" in item for item in found)
    assert any("\u00a3" in item for item in found)


def test_extract_currency_no_matches():
    assert extract_currency("nothing monetary here") == []


def test_extract_currency_empty_text():
    assert extract_currency("") == []


# ---------------------------------------------------------------------------
# Combined helper
# ---------------------------------------------------------------------------
def test_extract_patterns_returns_all_three_groups():
    text = (
        "Invoice 2026-10-10\nBill to accounts@glint.app\nTotal due: $1,250.75"
    )
    patterns = extract_patterns(text)
    assert set(patterns) == {"emails", "dates", "currency"}
    assert patterns["emails"] == ["accounts@glint.app"]
    assert patterns["dates"] == ["2026-10-10"]
    assert patterns["currency"] == ["$1,250.75"]
    assert pattern_total(patterns) == 3


def test_extract_patterns_on_text_without_matches():
    patterns = extract_patterns("just some words")
    assert patterns == {"emails": [], "dates": [], "currency": []}
    assert pattern_total(patterns) == 0


def test_extract_patterns_caps_the_number_of_matches():
    text = " ".join(f"user{i}@glint.app" for i in range(200))
    assert len(extract_patterns(text)["emails"]) == 40
