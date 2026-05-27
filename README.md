# Mercury GitHub Radar

Mercury GitHub Radar generates a static page of fast-moving GitHub repositories. It reuses the WatchEvent momentum model from `gh-trending`: ClickHouse GitHub Events provide recent and previous star counts, then the app computes velocity, acceleration, percent change, fastest-rising repos, and highest-velocity repos.

The generated site lives in `docs/`:

- `docs/data.json` contains the current rankings and README-derived enrichment.
- `docs/index.html` renders a polished static dashboard from that JSON.

## Local Usage

No secrets are required for a small local run. GitHub API enrichment works better if `gh` is authenticated or `GITHUB_TOKEN` is set, but the generator falls back to unauthenticated REST calls.

```bash
python -m pip install -e .
mercury-gh-radar generate
```

For a low-limit smoke run:

```bash
./scripts/run_update.sh --top 5 --source-limit 30 --stars 20 --min-recent 2
```

Open `docs/index.html` directly in a browser, or serve `docs/` with any static file server.

## Data Model

Each displayed repository includes:

- `repo_name`
- `total_stars`
- `stars_recent`
- `stars_prev`
- `velocity`
- `acceleration`
- `pct_change`
- `description`
- `language`
- `readme_summary`
- `readme_url`

`readme_summary` is derived from README content, not from the GitHub repository description. README responses are cached in `.cache/readmes.json` with a default 24-hour TTL. GitHub README calls are bounded to the repositories that appear in the displayed ranking sections.

## Generation

The default command:

```bash
mercury-gh-radar generate --window 7 --stars 200 --min-recent 5 --top 25
```

Useful options:

- `--source-limit`: maximum ClickHouse rows to rank before selecting displayed repos.
- `--readme-cache-ttl`: README cache TTL in seconds.
- `--skip-github`: generate from ClickHouse only, without GitHub metadata or README calls.
- `--data-path` and `--index-path`: customize generated output paths.

## GitHub Pages

`.github/workflows/pages.yml` runs daily, regenerates `docs/data.json`, commits the generated files when they change, and deploys `docs/` to GitHub Pages. It uses the built-in `GITHUB_TOKEN`; no extra repository secret is required.
