"""ClickHouse access for GitHub WatchEvent momentum metrics."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

CLICKHOUSE_URL = "https://sql-clickhouse.clickhouse.com/?user=play"


def build_query(window_days: int, min_stars: int, min_recent: int, limit: int = 200) -> str:
    """Build the WatchEvent query reused from the original gh-trending script."""
    return f"""\
SELECT
    repo_name,
    count() AS total_stars,
    countIf(created_at >= now() - INTERVAL {window_days} DAY) AS stars_recent,
    countIf(created_at < now() - INTERVAL {window_days} DAY) AS stars_prev,
    round(countIf(created_at >= now() - INTERVAL {window_days} DAY) / {window_days}.0, 1) AS velocity,
    toInt64(countIf(created_at >= now() - INTERVAL {window_days} DAY))
        - toInt64(countIf(created_at < now() - INTERVAL {window_days} DAY)) AS acceleration
FROM github.github_events
WHERE event_type = 'WatchEvent'
  AND created_at >= now() - INTERVAL {window_days * 2} DAY
GROUP BY repo_name
HAVING total_stars >= {min_stars} AND stars_recent >= {min_recent}
ORDER BY velocity DESC
LIMIT {limit}
FORMAT JSON"""


def query_clickhouse(query: str, retries: int = 3, timeout: int = 60) -> dict[str, Any]:
    body = query.encode("utf-8")
    request = urllib.request.Request(CLICKHOUSE_URL, data=body, method="POST")
    last_error = ""

    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            if attempt < retries:
                time.sleep(attempt)
                continue

    raise RuntimeError(f"ClickHouse query failed after {retries} attempts: {last_error}")
