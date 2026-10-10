"""History based analytics: a few real numbers and one chart.

Everything here is derived from rows that already exist in SQLite. Nothing is
estimated, simulated or invented, and an empty database is a normal situation
that produces a clean "no data" answer instead of an exception.

* :func:`compute_summary` uses **pandas** to aggregate the history.
* :func:`render_chart_png` uses **matplotlib** with the non-interactive ``Agg``
  backend to draw one small PNG (activity per day + file type distribution).

Concepts demonstrated: pandas aggregation, matplotlib figure creation,
dictionary building, conditions and defensive programming.
"""

from __future__ import annotations

import io
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import matplotlib

# Must be set before pyplot is imported: no GUI is available or needed.
matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import ticker as mpl_ticker  # noqa: E402
import pandas as pd  # noqa: E402

logger = logging.getLogger("glint.analytics")

# Brand palette so the generated chart matches the UI.
COLOR_CANVAS = "#191C22"
COLOR_RAISED = "#20242B"
COLOR_TEXT = "#F4F5F1"
COLOR_MUTED = "#989DA8"
COLOR_ACCENT = "#C7F36B"
COLOR_GRID = "#2D323B"

ACTIVITY_WINDOW_DAYS = 14


def empty_summary() -> Dict[str, Any]:
    """The analytics payload used when nothing has been processed yet."""
    return {
        "has_data": False,
        "total_documents": 0,
        "total_pages": 0,
        "total_characters": 0,
        "average_duration_ms": 0.0,
        "fastest_duration_ms": 0.0,
        "slowest_duration_ms": 0.0,
        "most_common_file_type": None,
        "file_type_counts": {},
        "last_processed_at": None,
    }


def compute_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate stored history rows into the numbers shown in the UI."""
    if not rows:
        return empty_summary()

    frame = pd.DataFrame(rows)

    # Defensive: the columns always exist, but their types come from SQLite.
    frame["pages"] = pd.to_numeric(frame["pages"], errors="coerce").fillna(0)
    frame["duration_ms"] = pd.to_numeric(
        frame["duration_ms"], errors="coerce"
    ).fillna(0.0)
    frame["char_count"] = pd.to_numeric(
        frame["char_count"], errors="coerce"
    ).fillna(0)

    type_counts = frame["file_type"].value_counts()
    # ``idxmax`` on ties is order dependent; sort for a stable answer.
    most_common = (
        sorted(type_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
        if not type_counts.empty
        else None
    )

    summary = {
        "has_data": True,
        "total_documents": int(len(frame)),
        "total_pages": int(frame["pages"].sum()),
        "total_characters": int(frame["char_count"].sum()),
        "average_duration_ms": round(float(frame["duration_ms"].mean()), 1),
        "fastest_duration_ms": round(float(frame["duration_ms"].min()), 1),
        "slowest_duration_ms": round(float(frame["duration_ms"].max()), 1),
        "most_common_file_type": most_common,
        "file_type_counts": {
            str(name): int(value) for name, value in type_counts.items()
        },
        "last_processed_at": max(str(value) for value in frame["created_at"]),
    }
    return summary


def _daily_activity(rows: List[Dict[str, Any]], days: int) -> List[tuple]:
    """Return ``[(date, document_count), ...]`` for the last ``days`` days."""
    today = datetime.now(timezone.utc).date()
    buckets: Dict[str, int] = {}
    for row in rows:
        stamp = str(row.get("created_at") or "")
        if len(stamp) < 10:
            continue
        day = stamp[:10]
        buckets[day] = buckets.get(day, 0) + 1

    series = []
    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)
        key = day.isoformat()
        series.append((key, buckets.get(key, 0)))
    return series


def _style_axis(axis) -> None:
    """Apply the Glint dark theme to one matplotlib axis."""
    axis.set_facecolor(COLOR_CANVAS)
    for spine in axis.spines.values():
        spine.set_color(COLOR_GRID)
    axis.tick_params(colors=COLOR_MUTED, labelsize=8)
    axis.xaxis.label.set_color(COLOR_MUTED)
    axis.yaxis.label.set_color(COLOR_MUTED)
    axis.title.set_color(COLOR_TEXT)
    axis.grid(True, color=COLOR_GRID, linewidth=0.6, alpha=0.6)
    axis.set_axisbelow(True)


def _empty_state_figure(message: str) -> bytes:
    """A small, honest "no data yet" image (never a fabricated chart)."""
    figure = plt.figure(figsize=(9.4, 3.4), dpi=110)
    figure.patch.set_facecolor(COLOR_CANVAS)
    axis = figure.add_subplot(111)
    _style_axis(axis)
    axis.set_xticks([])
    axis.set_yticks([])
    axis.text(
        0.5,
        0.55,
        message,
        ha="center",
        va="center",
        color=COLOR_MUTED,
        fontsize=12,
    )
    axis.text(
        0.5,
        0.34,
        "Process a document in the Workspace to see real statistics here.",
        ha="center",
        va="center",
        color=COLOR_MUTED,
        fontsize=8.5,
        alpha=0.8,
    )
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", facecolor=figure.get_facecolor())
    plt.close(figure)
    return buffer.getvalue()


def render_chart_png(rows: List[Dict[str, Any]]) -> Optional[bytes]:
    """Build the analytics chart. Returns PNG bytes (never raises on no data)."""
    if not rows:
        return _empty_state_figure("No processing history yet")

    try:
        activity = _daily_activity(rows, ACTIVITY_WINDOW_DAYS)
        summary = compute_summary(rows)
        type_counts: Dict[str, int] = summary["file_type_counts"]

        figure, (left, right) = plt.subplots(
            1, 2, figsize=(9.4, 3.4), dpi=110, gridspec_kw={"width_ratios": [2, 1]}
        )
        figure.patch.set_facecolor(COLOR_CANVAS)
        figure.subplots_adjust(wspace=0.32)

        # --- left: documents per day -----------------------------------
        _style_axis(left)
        labels = [day_key[5:] for day_key, _count in activity]  # MM-DD
        values = [count for _, count in activity]
        # Numeric x positions keep the axis purely ordinal (no date guessing).
        positions = list(range(len(values)))
        bars = left.bar(
            positions,
            values,
            color=COLOR_ACCENT,
            edgecolor="none",
            width=0.62,
        )
        left.set_title(
            f"Documents processed - last {ACTIVITY_WINDOW_DAYS} days",
            fontsize=9.5,
            loc="left",
            pad=8,
        )
        left.set_ylabel("documents", fontsize=8)
        step = max(1, len(labels) // 7)
        left.set_xticks(positions[::step])
        left.set_xticklabels(labels[::step], rotation=0)
        left.set_xlim(-0.7, len(values) - 0.3)
        if values:
            top = max(values)
            left.set_ylim(0, max(1, top) + 1)
            left.yaxis.set_major_locator(
                mpl_ticker.MaxNLocator(integer=True, nbins=min(5, top + 1))
            )
        for bar, value in zip(bars, values):
            if value:
                left.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.08,
                    str(value),
                    ha="center",
                    va="bottom",
                    color=COLOR_MUTED,
                    fontsize=7.5,
                )

        # --- right: file type distribution ------------------------------
        _style_axis(right)
        names = list(type_counts.keys())
        counts = [type_counts[name] for name in names]
        if names:
            right.barh(
                names, counts, color=COLOR_ACCENT, edgecolor="none", height=0.5
            )
            right.invert_yaxis()
            right.xaxis.set_major_locator(
                mpl_ticker.MaxNLocator(integer=True, nbins=4)
            )
            for index, value in enumerate(counts):
                right.text(
                    value + 0.08,
                    index,
                    str(value),
                    va="center",
                    color=COLOR_MUTED,
                    fontsize=7.5,
                )
        right.set_title("File types", fontsize=9.5, loc="left", pad=8)
        right.set_xlabel("documents", fontsize=8)

        buffer = io.BytesIO()
        figure.savefig(
            buffer,
            format="png",
            facecolor=figure.get_facecolor(),
            bbox_inches="tight",
            pad_inches=0.25,
        )
        plt.close(figure)
        return buffer.getvalue()
    except Exception:
        logger.exception("Chart rendering failed")
        plt.close("all")
        return _empty_state_figure("Chart unavailable")
