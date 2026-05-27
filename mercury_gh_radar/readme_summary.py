"""README summarization heuristics."""

from __future__ import annotations

import re
from html import unescape

BOILERPLATE_HEADINGS = {
    "installation",
    "install",
    "usage",
    "quickstart",
    "getting started",
    "license",
    "contributing",
    "development",
    "api",
    "docs",
    "documentation",
}


def summarize_readme(markdown: str, fallback: str = "", max_chars: int = 260) -> str:
    text = _strip_markdown_noise(markdown)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    candidates: list[str] = []

    for paragraph in paragraphs[:18]:
        normalized = _normalize_space(paragraph)
        if not normalized or _is_boilerplate(normalized):
            continue
        if len(normalized.split()) < 5:
            continue
        candidates.append(normalized)

    if not candidates and fallback:
        candidates.append(_normalize_space(fallback))
    if not candidates:
        return ""

    summary = candidates[0]
    summary = re.sub(r"^(#\s*)?[A-Za-z0-9_.-]+\s+is\s+", "", summary, flags=re.I)
    return _truncate(summary, max_chars)


def _strip_markdown_noise(markdown: str) -> str:
    text = unescape(markdown.replace("\r\n", "\n"))
    text = re.sub(r"```.*?```", "\n", text, flags=re.S)
    text = re.sub(r"<!--.*?-->", "\n", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"!\[[^\]]*]\([^)]*\)", " ", text)
    text = re.sub(r"\[[^\]]+]\(([^)]*)\)", lambda m: m.group(0).split("](", 1)[0][1:], text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"^\s{0,3}>\s?", "", text, flags=re.M)
    text = re.sub(r"^\s{0,3}[-*+]\s+", "", text, flags=re.M)
    text = re.sub(r"^\s{0,3}\d+\.\s+", "", text, flags=re.M)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"[*_~]{1,3}", "", text)
    text = re.sub(r"^\s*(?:\[!\[[^\n]+|!\[[^\n]+|https?://\S+)\s*$", "", text, flags=re.M)
    return text


def _is_boilerplate(text: str) -> bool:
    lowered = text.strip(" :#").lower()
    if lowered in BOILERPLATE_HEADINGS:
        return True
    if lowered.startswith(("language:", "languages:", "language ", "languages ", "check out ", "follow me ")):
        return True
    if any(marker in lowered for marker in ("quickstart · docs", "docs ·", "youtube ·", "discord", "sponsor", "star history")):
        return True
    if "check out my new project" in lowered or "follow me on" in lowered:
        return True
    if text.count("|") >= 3:
        return True
    if text.count(" / ") >= 2:
        return True
    if lowered.startswith(("npm install", "pip install", "docker run", "git clone")):
        return True
    return False


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    clipped = text[: max_chars - 1].rsplit(" ", 1)[0].rstrip(".,;:")
    return clipped + "..."
