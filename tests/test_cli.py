"""Regression tests for command-line defaults."""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from mercury_gh_radar import cli


class CliDefaultsTest(unittest.TestCase):
    @patch("mercury_gh_radar.cli.query_clickhouse")
    @patch("mercury_gh_radar.cli.build_query")
    def test_default_activity_floor_keeps_rankings_populated(
        self, build_query, query_clickhouse
    ) -> None:
        build_query.return_value = "query"
        query_clickhouse.return_value = {
            "data": [
                {
                    "repo_name": "example/project",
                    "total_stars": "20",
                    "stars_recent": "12",
                    "stars_prev": "8",
                    "velocity": 1.7,
                    "acceleration": "4",
                }
            ]
        }

        output = io.StringIO()
        with redirect_stdout(output):
            result = cli.main(["--json", "--skip-github"])

        self.assertEqual(result, 0)
        build_query.assert_called_once_with(7, 20, 5, 200)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["min_stars"], 20)
        self.assertEqual(len(payload["fastest_rising"]), 1)
        self.assertEqual(len(payload["highest_velocity"]), 1)


if __name__ == "__main__":
    unittest.main()
