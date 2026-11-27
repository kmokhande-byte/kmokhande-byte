#!/usr/bin/env python3
"""Update the latest repositories table in README.md from the GitHub API."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

START_MARKER = "<!--START_SECTION:latest_repos-->"
END_MARKER = "<!--END_SECTION:latest_repos-->"
MAX_REPOS = 8
MAX_DESC_LEN = 110


def fetch_repos(username: str, token: str | None = None) -> list[dict]:
    """Fetch public non-fork owner repositories sorted by most recently pushed."""
    url = f"https://api.github.com/users/{username}/repos?sort=pushed&per_page=100&type=owner"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{username}-profile-readme-updater",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            repos = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"GitHub API returned HTTP {exc.code}: {body}") from exc

    filtered = [
        repo
        for repo in repos
        if not repo.get("private")
        and not repo.get("fork")
        and repo.get("name", "").lower() != username.lower()
    ]
    filtered.sort(key=lambda r: r.get("pushed_at") or "", reverse=True)
    return filtered[:MAX_REPOS]


def sanitize_cell(text: str | None, fallback: str = "—") -> str:
    """Escape Markdown table separators and collapse whitespace."""
    if not text:
        return fallback
    cleaned = " ".join(text.replace("|", "\\|").split())
    if len(cleaned) > MAX_DESC_LEN:
        cleaned = cleaned[: MAX_DESC_LEN - 1].rstrip() + "…"
    return cleaned


def build_table(repos: list[dict]) -> str:
    """Render a GitHub-flavored Markdown table for the given repositories."""
    if not repos:
        return "_No public repositories found yet._"

    lines = [
        "| Repository | Description | Language | Stars | Last Pushed |",
        "| :--- | :--- | :--- | :---: | :---: |",
    ]
    for repo in repos:
        name = sanitize_cell(repo.get("name"), "unknown")
        url = repo.get("html_url", "")
        desc = sanitize_cell(repo.get("description"), "No description provided.")
        lang = sanitize_cell(repo.get("language"), "—")
        stars = int(repo.get("stargazers_count") or 0)
        pushed = (repo.get("pushed_at") or "")[:10] or "—"
        lines.append(f"| [**{name}**]({url}) | {desc} | `{lang}` | ⭐ {stars} | `{pushed}` |")
    return "\n".join(lines)


def update_readme(readme_path: Path, table_md: str) -> bool:
    """Replace the marked section in README.md and return True if file changed."""
    original = readme_path.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"({re.escape(START_MARKER)})(.*?)({re.escape(END_MARKER)})",
        flags=re.DOTALL,
    )
    if not pattern.search(original):
        raise ValueError(
            f"Missing {START_MARKER} / {END_MARKER} markers in {readme_path}"
        )

    replacement = f"{START_MARKER}\n\n{table_md}\n\n{END_MARKER}"
    updated = pattern.sub(lambda _: replacement, original, count=1)
    if updated == original:
        return False

    readme_path.write_text(updated, encoding="utf-8")
    return True


def main() -> int:
    username = os.environ.get("GITHUB_USERNAME", "kmokhande-byte").strip()
    token = os.environ.get("GITHUB_TOKEN") or None
    readme_path = Path(os.environ.get("README_PATH", "README.md"))

    repos = fetch_repos(username, token=token)
    table_md = build_table(repos)
    changed = update_readme(readme_path, table_md)
    print(f"Fetched {len(repos)} repos for @{username}. README updated: {changed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
