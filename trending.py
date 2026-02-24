#!/usr/bin/env python3
"""Find GitHub repos with the most star momentum using the ClickHouse GitHub Events API."""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import date

CLICKHOUSE_URL = "https://gh-api.clickhouse.tech/?user=play"
PCT_CAP = 9999
BREAKOUT_THRESHOLD = 3  # prev stars below this = "breakout" repo


# ── ClickHouse query ─────────────────────────────────────────────────────────


def build_query(window_days, min_stars, min_recent):
    return f"""\
SELECT
    repo_name,
    count() AS total_stars,
    countIf(created_at >= now() - INTERVAL {window_days} DAY) AS stars_recent,
    countIf(created_at >= now() - INTERVAL {window_days * 2} DAY
        AND created_at < now() - INTERVAL {window_days} DAY) AS stars_prev,
    round(countIf(created_at >= now() - INTERVAL {window_days} DAY) / {window_days}.0, 1) AS velocity,
    toInt64(countIf(created_at >= now() - INTERVAL {window_days} DAY))
        - toInt64(countIf(created_at >= now() - INTERVAL {window_days * 2} DAY
            AND created_at < now() - INTERVAL {window_days} DAY)) AS acceleration
FROM github_events
WHERE event_type = 'WatchEvent'
GROUP BY repo_name
HAVING total_stars >= {min_stars} AND stars_recent >= {min_recent}
ORDER BY velocity DESC
LIMIT 200
FORMAT JSON"""


def query_clickhouse(query):
    curl = shutil.which("curl")
    if not curl:
        print("Error: curl not found in PATH", file=sys.stderr)
        sys.exit(1)

    result = subprocess.run(
        [curl, "-sS", "--fail-with-body", "--max-time", "30",
         CLICKHOUSE_URL, "--data-binary", query],
        capture_output=True, text=True,
    )

    if result.returncode != 0:
        msg = result.stderr.strip() or result.stdout.strip() or f"curl exited {result.returncode}"
        print(f"Error: {msg}", file=sys.stderr)
        sys.exit(1)

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        print(f"Error parsing response: {e}", file=sys.stderr)
        print(result.stdout[:500], file=sys.stderr)
        sys.exit(1)


# ── GitHub API ───────────────────────────────────────────────────────────────


def fetch_repo_info(repo_names):
    """Fetch stars, description, and language from GitHub for a list of repos."""
    if not repo_names:
        return {}

    gh = shutil.which("gh")
    if gh:
        info = _fetch_info_graphql(gh, repo_names)
        if info is not None:
            return info

    return _fetch_info_rest(repo_names)


def _fetch_info_graphql(gh, repo_names):
    aliases = []
    for i, name in enumerate(repo_names):
        parts = name.split("/", 1)
        if len(parts) != 2:
            continue
        owner, repo = parts
        aliases.append(
            f'r{i}: repository(owner: "{owner}", name: "{repo}") '
            f'{{ stargazerCount description primaryLanguage {{ name }} }}'
        )

    if not aliases:
        return None

    info = {}
    for chunk_start in range(0, len(aliases), 50):
        chunk = aliases[chunk_start:chunk_start + 50]
        query = "{ " + " ".join(chunk) + " }"
        result = subprocess.run(
            [gh, "api", "graphql", "-f", f"query={query}"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            return None
        try:
            data = json.loads(result.stdout).get("data", {})
        except (json.JSONDecodeError, AttributeError):
            return None
        for key, val in data.items():
            if not val:
                continue
            idx = int(key[1:])
            lang = val.get("primaryLanguage")
            info[repo_names[idx]] = {
                "stars": val.get("stargazerCount"),
                "description": val.get("description") or "",
                "language": lang["name"] if lang else "",
            }

    return info


def _fetch_info_rest(repo_names):
    curl = shutil.which("curl")
    if not curl:
        return {}

    info = {}
    for name in repo_names:
        result = subprocess.run(
            [curl, "-sS", "--max-time", "5",
             "-H", "Accept: application/vnd.github+json",
             f"https://api.github.com/repos/{name}"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            continue
        try:
            data = json.loads(result.stdout)
            if "stargazers_count" in data:
                info[name] = {
                    "stars": data["stargazers_count"],
                    "description": data.get("description") or "",
                    "language": data.get("language") or "",
                }
        except (json.JSONDecodeError, KeyError):
            continue
    return info


# ── Formatting ───────────────────────────────────────────────────────────────


def compact_num(n):
    if n < 1000:
        return str(n)
    if n < 100_000:
        return f"{n / 1000:.1f}k"
    if n < 1_000_000:
        return f"{n // 1000}k"
    return f"{n / 1_000_000:.1f}M"


def format_pct(pct, is_breakout, use_color):
    GREEN = "\033[32m" if use_color else ""
    RED = "\033[31m" if use_color else ""
    YELLOW = "\033[33m" if use_color else ""
    RESET = "\033[0m" if use_color else ""

    if is_breakout:
        raw = "+\u221e"
        colored = f"{YELLOW}+\u221e{RESET}"
    elif pct > 0:
        raw = f"+{pct}%"
        colored = f"{GREEN}{raw}{RESET}"
    elif pct < 0:
        raw = f"{pct}%"
        colored = f"{RED}{raw}{RESET}"
    else:
        raw = "0%"
        colored = raw
    return colored, raw


def pick_rising(rows, n):
    """Select rows for the rising table: breakout repos first, then by % change."""
    max_breakout = max(3, n // 3)
    breakout = sorted(
        [r for r in rows if r["stars_prev"] < BREAKOUT_THRESHOLD],
        key=lambda r: r["stars_recent"], reverse=True,
    )[:max_breakout]
    rest = sorted(
        [r for r in rows if r["stars_prev"] >= BREAKOUT_THRESHOLD],
        key=lambda r: r["pct_change"], reverse=True,
    )
    return (breakout + rest)[:n]


def format_table(rows, sort_key, n, window_days, use_color, term_width):
    if sort_key == "acceleration":
        rows = pick_rising(rows, n)
        title = "FASTEST RISING (% change in starring rate)"
    else:
        rows = sorted(rows, key=lambda r: r["velocity"], reverse=True)[:n]
        title = "HIGHEST VELOCITY (most stars/day)"

    if not rows:
        return ""

    num_w = len(str(n))
    BOLD = "\033[1m" if use_color else ""
    DIM = "\033[2m" if use_color else ""
    WHITE = "\033[97m" if use_color else ""
    RESET = "\033[0m" if use_color else ""

    w = min(term_width or 80, 120)
    sep = "\u2500" * w
    lines = []
    lines.append(f"\n{BOLD}{title}{RESET}")
    lines.append(sep)

    stats_hdr = f"{'total':>6}  {'%dd' % window_days:>5}  {'prev':>5}  {'vel/d':>6}  {'chg%':>7}"
    lines.append(f"{DIM}{' ' * (w - len(stats_hdr))}{stats_hdr}{RESET}")
    lines.append(sep)

    stats_width = 39  # fixed width of the stats columns (including leading 2-space gap)
    breakout_boundary_shown = False

    for i, r in enumerate(rows, 1):
        if (sort_key == "acceleration" and not breakout_boundary_shown
                and r["stars_prev"] >= BREAKOUT_THRESHOLD
                and any(p["stars_prev"] < BREAKOUT_THRESHOLD for p in rows[:i - 1])):
            breakout_boundary_shown = True
            lines.append(f"{DIM}{'  \u2504 established repos ':─<{w}}{RESET}")

        name = r["repo_name"]
        is_breakout = r["stars_prev"] < BREAKOUT_THRESHOLD

        pct_colored, pct_raw = format_pct(r["pct_change"], is_breakout, use_color)
        pct_field = " " * (7 - len(pct_raw)) + pct_colored

        stats = (
            f"  {compact_num(r['total_stars']):>6}  {r['stars_recent']:>5}  {r['stars_prev']:>5}"
            f"  {r['velocity']:>6}  {pct_field}"
        )

        url = f"https://github.com/{name}"
        prefix = f"{i:>{num_w}}  "
        url_space = w - len(prefix) - stats_width
        display_url = url if len(url) <= url_space else url[:url_space - 1] + "\u2026"

        if use_color:
            lines.append(f"{prefix}{WHITE}{display_url:<{url_space}}{RESET}{stats}")
        else:
            lines.append(f"{prefix}{display_url:<{url_space}}{stats}")

        # Language + description
        desc = r.get("description", "").strip()
        lang = r.get("language", "")
        indent = "    "
        max_meta = w - len(indent) - 4

        if lang and desc:
            lang_prefix = f"[{lang}] "
            remaining = max_meta - len(lang_prefix)
            if len(desc) > remaining:
                desc = desc[:remaining - 1] + "\u2026"
            if use_color:
                lines.append(f"{indent}{DIM}{lang_prefix}{desc}{RESET}")
            else:
                lines.append(f"{indent}{lang_prefix}{desc}")
        elif lang:
            lines.append(f"{indent}{DIM}[{lang}]{RESET}" if use_color else f"{indent}[{lang}]")
        elif desc:
            if len(desc) > max_meta:
                desc = desc[:max_meta - 1] + "\u2026"
            lines.append(f"{indent}{DIM}{desc}{RESET}" if use_color else f"{indent}{desc}")

    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Find trending GitHub repos by star momentum.")
    parser.add_argument("--sort", choices=["velocity", "acceleration", "both"], default="both",
                        help="Ranking to show (default: both)")
    parser.add_argument("-w", "--window", type=int, default=7, metavar="DAYS",
                        help="Window size in days (default: 7)")
    parser.add_argument("-s", "--stars", type=int, default=200, metavar="MIN",
                        help="Minimum total stars (default: 200)")
    parser.add_argument("-n", "--top", type=int, default=25, metavar="N",
                        help="Number of repos per ranking (default: 25)")
    parser.add_argument("--min-recent", type=int, default=5, metavar="N",
                        help="Minimum stars in recent window (default: 5)")
    parser.add_argument("--json", action="store_true", dest="json_out",
                        help="Output raw JSON")
    args = parser.parse_args()

    # Query ClickHouse for star events
    query = build_query(args.window, args.stars, args.min_recent)
    data = query_clickhouse(query)

    rows = data.get("data", [])
    if not rows:
        print("No results found.", file=sys.stderr)
        sys.exit(0)

    for r in rows:
        r["total_stars"] = int(r["total_stars"])
        r["stars_recent"] = int(r["stars_recent"])
        r["stars_prev"] = int(r["stars_prev"])
        r["velocity"] = float(r["velocity"])
        r["acceleration"] = int(r["acceleration"])
        if r["stars_prev"] >= BREAKOUT_THRESHOLD:
            r["pct_change"] = round((r["stars_recent"] - r["stars_prev"]) / r["stars_prev"] * 100)
        else:
            r["pct_change"] = PCT_CAP

    # Predict which repos will be displayed to minimize GitHub API calls
    by_rising = pick_rising(rows, args.top)
    by_vel = sorted(rows, key=lambda r: r["velocity"], reverse=True)[:args.top]
    if args.sort == "acceleration":
        display_repos = {r["repo_name"] for r in by_rising}
    elif args.sort == "velocity":
        display_repos = {r["repo_name"] for r in by_vel}
    else:
        display_repos = {r["repo_name"] for r in by_rising} | {r["repo_name"] for r in by_vel}

    # Enrich with real star counts, descriptions, and languages from GitHub
    print("Fetching repo info from GitHub...", end="", flush=True, file=sys.stderr)
    repo_info = fetch_repo_info(list(display_repos))
    print(f" {len(repo_info)}/{len(display_repos)} repos", file=sys.stderr)

    for r in rows:
        info = repo_info.get(r["repo_name"])
        if info:
            r["total_stars"] = info["stars"]
            r["description"] = info["description"]
            r["language"] = info["language"]
        else:
            r.setdefault("description", "")
            r.setdefault("language", "")

    if args.json_out:
        if args.sort == "acceleration":
            out = sorted(rows, key=lambda r: r["pct_change"], reverse=True)[:args.top]
        elif args.sort == "velocity":
            out = sorted(rows, key=lambda r: r["velocity"], reverse=True)[:args.top]
        else:
            out = rows[:args.top * 2]
        json.dump(out, sys.stdout, indent=2)
        print()
        return

    use_color = sys.stdout.isatty()
    try:
        term_width = os.get_terminal_size().columns
    except OSError:
        term_width = 80

    header = f"GitHub Trending Repos ({date.today().strftime('%b %d, %Y')})"
    sub = f"Repos with {args.stars}+ total stars, {args.window}-day window"

    BOLD = "\033[1m" if use_color else ""
    RESET = "\033[0m" if use_color else ""

    print(f"\n{BOLD}{header}{RESET}")
    print(sub)

    if args.sort in ("both", "acceleration"):
        print(format_table(rows, "acceleration", args.top, args.window, use_color, term_width))

    if args.sort in ("both", "velocity"):
        print(format_table(rows, "velocity", args.top, args.window, use_color, term_width))

    print()


if __name__ == "__main__":
    main()
