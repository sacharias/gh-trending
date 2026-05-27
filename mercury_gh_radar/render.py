"""Static JSON and HTML rendering."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .metrics import BREAKOUT_THRESHOLD, PCT_CAP, pick_rising, pick_velocity


def build_payload(
    rows: list[dict[str, Any]],
    *,
    window: int,
    min_stars: int,
    min_recent: int,
    top: int,
    source_limit: int,
) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return {
        "generated_at": generated_at,
        "window_days": window,
        "min_stars": min_stars,
        "min_recent": min_recent,
        "source_limit": source_limit,
        "top": top,
        "fastest_rising": pick_rising(rows, top),
        "highest_velocity": pick_velocity(rows, top),
    }


def write_data(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_index(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(INDEX_HTML, encoding="utf-8")


def pct_label(row: dict[str, Any]) -> str:
    if row["stars_prev"] < BREAKOUT_THRESHOLD or row.get("pct_change") == PCT_CAP:
        return "+inf"
    pct = int(row["pct_change"])
    return f"+{pct}%" if pct > 0 else f"{pct}%"


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mercury GitHub Radar</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #17202a;
      --muted: #607080;
      --line: #d9e0e7;
      --paper: #fafbfc;
      --panel: #ffffff;
      --accent: #d04f2f;
      --accent-2: #137c7f;
      --good: #16794c;
      --shadow: 0 14px 35px rgba(22, 32, 42, .08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--paper);
      color: var(--ink);
      line-height: 1.45;
    }
    a { color: inherit; text-decoration: none; }
    a:hover { color: var(--accent); }
    header {
      border-bottom: 1px solid var(--line);
      background: linear-gradient(180deg, #fff 0%, #f4f7f8 100%);
    }
    .wrap { max-width: 1180px; margin: 0 auto; padding: 0 22px; }
    .mast {
      min-height: 38vh;
      display: grid;
      align-content: center;
      gap: 22px;
      padding: 54px 0 44px;
    }
    .kicker {
      color: var(--accent-2);
      font-size: 13px;
      font-weight: 800;
      letter-spacing: .08em;
      text-transform: uppercase;
    }
    h1 {
      margin: 0;
      max-width: 820px;
      font-size: clamp(42px, 7vw, 86px);
      line-height: .95;
      letter-spacing: 0;
    }
    .subhead {
      max-width: 760px;
      margin: 0;
      color: var(--muted);
      font-size: 18px;
    }
    .toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      min-height: 34px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 6px 12px;
      background: rgba(255,255,255,.8);
      color: var(--muted);
      font-size: 13px;
      font-weight: 650;
    }
    main { padding: 34px 0 56px; }
    .section-head {
      display: flex;
      justify-content: space-between;
      gap: 18px;
      align-items: end;
      margin: 28px 0 14px;
    }
    h2 { margin: 0; font-size: 24px; letter-spacing: 0; }
    .section-note { margin: 0; color: var(--muted); font-size: 14px; }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(310px, 1fr));
      gap: 14px;
    }
    .repo {
      min-height: 248px;
      display: flex;
      flex-direction: column;
      gap: 14px;
      padding: 18px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: var(--shadow);
    }
    .repo-top {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 14px;
      align-items: start;
    }
    .repo-name {
      overflow-wrap: anywhere;
      font-size: 18px;
      font-weight: 800;
      line-height: 1.2;
    }
    .rank {
      width: 36px;
      height: 36px;
      display: grid;
      place-items: center;
      border-radius: 50%;
      background: #eef5f5;
      color: var(--accent-2);
      font-weight: 850;
      font-size: 14px;
    }
    .summary {
      flex: 1;
      margin: 0;
      color: #283541;
      font-size: 15px;
    }
    .meta {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: auto;
    }
    .chip {
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 5px 9px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 720;
      background: #fff;
    }
    .chip.hot { color: var(--accent); border-color: rgba(208, 79, 47, .3); background: #fff7f4; }
    .chip.good { color: var(--good); border-color: rgba(22, 121, 76, .28); background: #f3fbf7; }
    .links {
      display: flex;
      gap: 12px;
      padding-top: 2px;
      font-size: 13px;
      font-weight: 760;
    }
    footer {
      border-top: 1px solid var(--line);
      padding: 24px 0 34px;
      color: var(--muted);
      font-size: 13px;
    }
    .error {
      padding: 18px;
      border: 1px solid #f0b8a8;
      border-radius: 8px;
      background: #fff7f4;
      color: #85351f;
      font-weight: 650;
    }
    @media (max-width: 720px) {
      .wrap { padding: 0 16px; }
      .mast { padding: 42px 0 32px; }
      .section-head { display: block; }
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <div class="wrap mast">
      <div class="kicker">Mercury GitHub Radar</div>
      <h1>Fast-moving open source repositories.</h1>
      <p class="subhead">Star momentum from ClickHouse GitHub Events, enriched with README-derived summaries for the repositories shown here.</p>
      <div class="toolbar" id="stats"></div>
    </div>
  </header>
  <main class="wrap">
    <div id="app"></div>
  </main>
  <footer>
    <div class="wrap">Generated from public GitHub WatchEvent data. README summaries are heuristic and cached between runs.</div>
  </footer>
  <script>
    const fmt = new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 });

    function pctLabel(repo) {
      if (repo.stars_prev < 3 || repo.pct_change === 9999) return "+inf";
      return repo.pct_change > 0 ? `+${repo.pct_change}%` : `${repo.pct_change}%`;
    }

    function repoCard(repo, index) {
      const url = `https://github.com/${repo.repo_name}`;
      const summary = repo.readme_summary || repo.description || "No README summary available.";
      const readmeLink = repo.readme_url ? `<a href="${repo.readme_url}">README</a>` : "";
      return `<article class="repo">
        <div class="repo-top">
          <a class="repo-name" href="${url}">${repo.repo_name}</a>
          <div class="rank">${index + 1}</div>
        </div>
        <p class="summary">${escapeHtml(summary)}</p>
        <div class="meta">
          <span class="chip hot">${pctLabel(repo)}</span>
          <span class="chip good">${repo.velocity} stars/day</span>
          <span class="chip">${repo.stars_recent} recent</span>
          <span class="chip">${repo.stars_prev} previous</span>
          <span class="chip">${fmt.format(repo.total_stars)} stars</span>
          ${repo.language ? `<span class="chip">${escapeHtml(repo.language)}</span>` : ""}
        </div>
        <div class="links"><a href="${url}">Repository</a>${readmeLink}</div>
      </article>`;
    }

    function renderSection(title, note, rows) {
      return `<section>
        <div class="section-head">
          <h2>${title}</h2>
          <p class="section-note">${note}</p>
        </div>
        <div class="grid">${rows.map(repoCard).join("")}</div>
      </section>`;
    }

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, (char) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      }[char]));
    }

    fetch("data.json", { cache: "no-store" })
      .then(response => {
        if (!response.ok) throw new Error(`Unable to load data.json (${response.status})`);
        return response.json();
      })
      .then(data => {
        document.getElementById("stats").innerHTML = `
          <span class="pill">Updated ${new Date(data.generated_at).toLocaleString()}</span>
          <span class="pill">${data.window_days}-day window</span>
          <span class="pill">${data.min_stars}+ event stars</span>
          <span class="pill">${data.min_recent}+ recent stars</span>`;
        document.getElementById("app").innerHTML = [
          renderSection("Fastest Rising", "Breakouts first, then highest change in starring rate.", data.fastest_rising || []),
          renderSection("Highest Velocity", "Most stars per day in the current window.", data.highest_velocity || [])
        ].join("");
      })
      .catch(error => {
        document.getElementById("app").innerHTML = `<div class="error">${escapeHtml(error.message)}</div>`;
      });
  </script>
</body>
</html>
"""
