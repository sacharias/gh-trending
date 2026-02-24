# gh-trending

Find GitHub repos with the most momentum right now.

Queries 3B+ GitHub events via [ClickHouse](https://gh-api.clickhouse.tech/) to compute two metrics:

- **Velocity** — stars per day in a recent window
- **% Change** — change in starring rate vs the previous window (finds breakout repos before they blow up)

Pulls in star counts, descriptions, and languages from the GitHub API.

## Install

```
curl -fsSL https://raw.githubusercontent.com/sacharias/gh-trending/main/install.sh | sh
```

Or manually with uv:

```
uv tool install gh-trending@git+https://github.com/sacharias/gh-trending
```

## Usage

```
gh-trending                        # Both rankings, 7-day window, 200+ stars, top 25
gh-trending --sort acceleration    # Only rising repos (by % change)
gh-trending --sort velocity        # Only highest velocity
gh-trending -w 3                   # 3-day window
gh-trending -s 1000                # Only repos with 1000+ total stars
gh-trending -n 10                  # Top 10 instead of 25
gh-trending --min-recent 20        # At least 20 stars in recent window
gh-trending --json                 # Raw JSON output
```

## Example output

```
GitHub Trending Repos (Feb 24, 2026)
Repos with 200+ total stars, 7-day window

FASTEST RISING (% change in starring rate)
────────────────────────────────────────────────────────────────────────────────
                                            total     7d   prev   vel/d     chg%
────────────────────────────────────────────────────────────────────────────────
1  https://github.com/some-org/new-thing       2.0k    601      0    85.9       +∞
    [Zig] Some cool new project that just appeared
2  https://github.com/another/breakout         1.7k    556      1    79.4       +∞
    [Swift] Another breakout repo
  ┄ established repos ──────────────────────────────────────────────────────────
3  https://github.com/rising/fast              2.3k    692      6    98.9  +11433%
    [TypeScript] An established repo gaining massive momentum
```

Breakout repos (near-zero previous activity) appear first with `+∞`, followed by established repos ranked by percentage growth. Colors show up in terminals and get stripped when piped.

## How it works

1. A single SQL query to ClickHouse compares starring activity in two adjacent time windows
2. Star counts, descriptions, and languages get pulled from GitHub's GraphQL API (`gh` CLI) or REST API (falls back to `curl`)
3. Two ranked tables are printed: fastest rising (% change) and highest velocity (stars/day)

## Requirements

- Python 3.9+
- `curl` (for ClickHouse queries)
- `gh` CLI (optional — authenticated GitHub API access with higher rate limits)
