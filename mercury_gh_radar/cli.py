"""Command-line interface for mercury-gh-radar."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .clickhouse import build_query, query_clickhouse
from .github import DEFAULT_CACHE_PATH, fetch_display_enrichment
from .metrics import apply_enrichment, displayed_repo_names, normalize_rows
from .render import build_payload, write_data, write_index

DEFAULT_MIN_ACTIVITY = 20


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mercury-gh-radar",
        description="Generate a static GitHub star-momentum radar.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=["generate"],
        default="generate",
        help="Command to run (default: generate)",
    )
    parser.add_argument("-w", "--window", type=int, default=7, help="Window size in days.")
    parser.add_argument(
        "-s",
        "--stars",
        type=int,
        default=DEFAULT_MIN_ACTIVITY,
        help=(
            "Minimum WatchEvents across the recent and previous windows "
            f"(default: {DEFAULT_MIN_ACTIVITY})."
        ),
    )
    parser.add_argument("--min-recent", type=int, default=5, help="Minimum stars in recent window.")
    parser.add_argument("-n", "--top", type=int, default=25, help="Repos per ranking.")
    parser.add_argument(
        "--sort",
        choices=["both", "acceleration", "velocity"],
        default="both",
        help="Which ranking set controls README/API enrichment.",
    )
    parser.add_argument(
        "--source-limit",
        type=int,
        default=200,
        help="Maximum rows returned by ClickHouse before ranking.",
    )
    parser.add_argument("--data-path", type=Path, default=Path("docs/data.json"))
    parser.add_argument("--index-path", type=Path, default=Path("docs/index.html"))
    parser.add_argument("--cache-path", type=Path, default=DEFAULT_CACHE_PATH)
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_out",
        help="Write generated JSON to stdout instead of docs files. Kept for gh-trending workflow compatibility.",
    )
    parser.add_argument(
        "--readme-cache-ttl",
        type=int,
        default=60 * 60 * 24,
        help="README cache TTL in seconds.",
    )
    parser.add_argument(
        "--skip-github",
        action="store_true",
        help="Skip GitHub metadata and README calls; useful for ClickHouse-only debugging.",
    )
    args = parser.parse_args(argv)

    if (
        args.window <= 0
        or args.stars < 0
        or args.min_recent < 0
        or args.top <= 0
        or args.source_limit <= 0
    ):
        parser.error(
            "--window, --top, and --source-limit must be positive; "
            "--stars and --min-recent cannot be negative"
        )

    print("Querying ClickHouse GitHub Events...", file=sys.stderr)
    query = build_query(args.window, args.stars, args.min_recent, args.source_limit)
    data = query_clickhouse(query)
    rows = normalize_rows(data.get("data", []))
    if not rows:
        raise SystemExit("No repositories matched the current thresholds.")

    display_names = displayed_repo_names(rows, args.top, args.sort)
    print(f"Selected {len(display_names)} displayed repos for GitHub enrichment.", file=sys.stderr)

    if not args.skip_github:
        enrichment = fetch_display_enrichment(
            display_names,
            cache_path=args.cache_path,
            ttl_seconds=args.readme_cache_ttl,
        )
        apply_enrichment(rows, enrichment)
        print(f"Enriched {len(enrichment)}/{len(display_names)} repos.", file=sys.stderr)

    payload = build_payload(
        rows,
        window=args.window,
        min_stars=args.stars,
        min_recent=args.min_recent,
        top=args.top,
        source_limit=args.source_limit,
    )
    if args.json_out:
        import json

        json.dump(payload, sys.stdout, indent=2)
        print()
        return 0

    write_data(payload, args.data_path)
    write_index(args.index_path)
    print(f"Wrote {args.data_path} and {args.index_path}.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
