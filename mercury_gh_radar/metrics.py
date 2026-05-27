"""Ranking and normalization for GitHub star momentum."""

from __future__ import annotations

from typing import Any

PCT_CAP = 9999
BREAKOUT_THRESHOLD = 3


def normalize_rows(raw_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in raw_rows:
        row = dict(raw)
        row["total_stars"] = int(row["total_stars"])
        row["stars_recent"] = int(row["stars_recent"])
        row["stars_prev"] = int(row["stars_prev"])
        row["velocity"] = float(row["velocity"])
        row["acceleration"] = int(row["acceleration"])
        if row["stars_prev"] >= BREAKOUT_THRESHOLD:
            row["pct_change"] = round(
                (row["stars_recent"] - row["stars_prev"]) / row["stars_prev"] * 100
            )
        else:
            row["pct_change"] = PCT_CAP
        row.setdefault("description", "")
        row.setdefault("language", "")
        row.setdefault("readme_summary", "")
        row.setdefault("readme_url", "")
        returnable = {k: row[k] for k in row}
        rows.append(returnable)
    return rows


def pick_rising(rows: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
    """Select rows for fastest-rising: breakout repos first, then by percent change."""
    max_breakout = max(3, n // 3)
    breakout = sorted(
        [r for r in rows if r["stars_prev"] < BREAKOUT_THRESHOLD],
        key=lambda r: r["stars_recent"],
        reverse=True,
    )[:max_breakout]
    rest = sorted(
        [r for r in rows if r["stars_prev"] >= BREAKOUT_THRESHOLD],
        key=lambda r: r["pct_change"],
        reverse=True,
    )
    return (breakout + rest)[:n]


def pick_velocity(rows: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda r: r["velocity"], reverse=True)[:n]


def displayed_repo_names(rows: list[dict[str, Any]], top: int, sort: str) -> list[str]:
    names: set[str] = set()
    if sort in ("both", "acceleration"):
        names.update(r["repo_name"] for r in pick_rising(rows, top))
    if sort in ("both", "velocity"):
        names.update(r["repo_name"] for r in pick_velocity(rows, top))
    return sorted(names)


def apply_enrichment(rows: list[dict[str, Any]], enrichment: dict[str, dict[str, Any]]) -> None:
    for row in rows:
        info = enrichment.get(row["repo_name"])
        if not info:
            continue
        if info.get("stars") is not None:
            row["total_stars"] = int(info["stars"])
        row["description"] = info.get("description") or ""
        row["language"] = info.get("language") or ""
        row["readme_summary"] = info.get("readme_summary") or ""
        row["readme_url"] = info.get("readme_url") or ""
