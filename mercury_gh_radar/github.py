"""GitHub metadata and README enrichment."""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .readme_summary import summarize_readme

GITHUB_API = "https://api.github.com"
DEFAULT_CACHE_PATH = Path(".cache/readmes.json")


def fetch_display_enrichment(
    repo_names: list[str],
    cache_path: Path = DEFAULT_CACHE_PATH,
    ttl_seconds: int = 60 * 60 * 24,
) -> dict[str, dict[str, Any]]:
    """Fetch GitHub metadata and README-derived summaries for displayed repos only."""
    if not repo_names:
        return {}

    token = _github_token()
    repo_info = _fetch_repo_info_graphql(repo_names) or _fetch_repo_info_rest(repo_names, token)
    readmes = _fetch_readmes(repo_names, repo_info, cache_path, ttl_seconds, token)

    merged: dict[str, dict[str, Any]] = {}
    for name in repo_names:
        info = repo_info.get(name, {})
        readme = readmes.get(name, {})
        merged[name] = {
            "stars": info.get("stars"),
            "description": info.get("description") or "",
            "language": info.get("language") or "",
            "readme_summary": readme.get("summary") or "",
            "readme_url": readme.get("html_url") or "",
        }
    return merged


def _fetch_repo_info_graphql(repo_names: list[str]) -> dict[str, dict[str, Any]] | None:
    gh = shutil.which("gh")
    if not gh:
        return None

    info: dict[str, dict[str, Any]] = {}
    for chunk_start in range(0, len(repo_names), 40):
        chunk_names = repo_names[chunk_start : chunk_start + 40]
        aliases = []
        alias_names: dict[str, str] = {}
        for i, name in enumerate(chunk_names):
            parts = name.split("/", 1)
            if len(parts) != 2:
                continue
            owner, repo = parts
            alias = f"r{i}"
            alias_names[alias] = name
            aliases.append(
                f'{alias}: repository(owner: "{_gql_escape(owner)}", name: "{_gql_escape(repo)}") '
                "{ stargazerCount description primaryLanguage { name } }"
            )
        if not aliases:
            continue

        result = subprocess.run(
            [gh, "api", "graphql", "-f", "query={ " + " ".join(aliases) + " }"],
            capture_output=True,
            text=True,
            timeout=45,
        )
        if result.returncode != 0:
            return None
        try:
            data = json.loads(result.stdout).get("data", {})
        except (json.JSONDecodeError, AttributeError):
            return None

        for alias, value in data.items():
            if not value:
                continue
            language = value.get("primaryLanguage")
            info[alias_names[alias]] = {
                "stars": value.get("stargazerCount"),
                "description": value.get("description") or "",
                "language": language.get("name") if language else "",
            }
    return info


def _fetch_repo_info_rest(repo_names: list[str], token: str | None) -> dict[str, dict[str, Any]]:
    info: dict[str, dict[str, Any]] = {}
    for name in repo_names:
        data = _http_json(f"{GITHUB_API}/repos/{name}", token=token, timeout=12)
        if not data or "stargazers_count" not in data:
            continue
        info[name] = {
            "stars": data.get("stargazers_count"),
            "description": data.get("description") or "",
            "language": data.get("language") or "",
        }
    return info


def _fetch_readmes(
    repo_names: list[str],
    repo_info: dict[str, dict[str, Any]],
    cache_path: Path,
    ttl_seconds: int,
    token: str | None,
) -> dict[str, dict[str, str]]:
    cache = _load_cache(cache_path)
    now = int(time.time())
    out: dict[str, dict[str, str]] = {}

    for name in repo_names:
        cached = cache.get(name)
        if cached and now - int(cached.get("fetched_at", 0)) < ttl_seconds:
            out[name] = {
                "summary": cached.get("summary", ""),
                "html_url": cached.get("html_url", ""),
            }
            continue

        readme = _fetch_readme_via_gh(name) or _fetch_readme_rest(name, token)
        fallback = repo_info.get(name, {}).get("description", "")
        if readme:
            summary = summarize_readme(readme["content"], fallback=fallback)
            record = {
                "summary": summary,
                "html_url": readme.get("html_url", ""),
                "download_url": readme.get("download_url", ""),
                "fetched_at": now,
            }
        else:
            record = {
                "summary": summarize_readme("", fallback=fallback),
                "html_url": "",
                "download_url": "",
                "fetched_at": now,
            }
        cache[name] = record
        out[name] = {"summary": record["summary"], "html_url": record["html_url"]}

    _save_cache(cache_path, cache)
    return out


def _fetch_readme_via_gh(name: str) -> dict[str, str] | None:
    gh = shutil.which("gh")
    if not gh:
        return None
    result = subprocess.run(
        [gh, "api", f"/repos/{name}/readme"],
        capture_output=True,
        text=True,
        timeout=20,
    )
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
        content = base64.b64decode(data.get("content", ""), validate=False).decode(
            "utf-8", errors="replace"
        )
    except (json.JSONDecodeError, ValueError, TypeError):
        return None
    return {
        "content": content,
        "html_url": data.get("html_url", ""),
        "download_url": data.get("download_url", ""),
    }


def _fetch_readme_rest(name: str, token: str | None) -> dict[str, str] | None:
    data = _http_json(f"{GITHUB_API}/repos/{name}/readme", token=token, timeout=15)
    if not data:
        return None
    content = ""
    encoded = data.get("content")
    if encoded:
        try:
            content = base64.b64decode(encoded).decode("utf-8", errors="replace")
        except ValueError:
            content = ""
    if not content and data.get("download_url"):
        content = _http_text(data["download_url"], token=token, timeout=15)
    if not content:
        return None
    return {
        "content": content,
        "html_url": data.get("html_url", ""),
        "download_url": data.get("download_url", ""),
    }


def _http_json(url: str, token: str | None, timeout: int) -> dict[str, Any] | None:
    text = _http_text(url, token=token, timeout=timeout, accept="application/vnd.github+json")
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _http_text(
    url: str,
    token: str | None,
    timeout: int,
    accept: str = "application/vnd.github+json",
) -> str:
    headers = {
        "Accept": accept,
        "User-Agent": "mercury-gh-radar",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError):
        return ""


def _github_token() -> str | None:
    if os.environ.get("GITHUB_TOKEN"):
        return os.environ["GITHUB_TOKEN"]
    gh = shutil.which("gh")
    if not gh:
        return None
    try:
        result = subprocess.run(
            [gh, "auth", "token"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    token = result.stdout.strip()
    return token if result.returncode == 0 and token else None


def _load_cache(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_cache(path: Path, cache: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _gql_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
