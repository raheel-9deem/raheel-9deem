#!/usr/bin/env python3
"""
Generate a full-history, exact-date commit activity SVG for the profile README.

It uses the public GitHub REST API and the workflow's GITHUB_TOKEN.
Dates are grouped by the commit author's UTC calendar date.
"""

import json
import os
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

USERNAME = os.environ.get("GITHUB_USERNAME", "raheel-9deem")
TOKEN = os.environ.get("GITHUB_TOKEN")
OUT = Path("assets/github-activity.svg")

API = "https://api.github.com"

def api_get(path, params=None):
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "raheel-profile-activity"
    })
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def all_repos():
    repos = []
    page = 1
    while True:
        data = api_get(f"/users/{USERNAME}/repos", {
            "per_page": 100,
            "page": page,
            "type": "all",
            "sort": "full_name"
        })
        if not data:
            break
        repos.extend(data)
        if len(data) < 100:
            break
        page += 1
    return [r for r in repos if not r.get("fork") and not r.get("archived")]

def commits_for_repo(repo):
    counts = Counter()
    page = 1
    owner = repo["owner"]["login"]
    name = repo["name"]

    while True:
        try:
            data = api_get(f"/repos/{owner}/{name}/commits", {
                "author": USERNAME,
                "per_page": 100,
                "page": page
            })
        except Exception as exc:
            print(f"Skipping {name}: {exc}")
            break

        if not data:
            break

        for item in data:
            commit = item.get("commit", {})
            author = commit.get("author") or {}
            date = author.get("date")
            if date:
                day = date[:10]
                counts[day] += 1

        if len(data) < 100:
            break
        page += 1

        # Avoid hammering the API on large histories.
        time.sleep(0.05)

    return counts

def make_svg(counts, repo_count):
    if not counts:
        return """<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="160" viewBox="0 0 1000 160">
<rect width="1000" height="160" rx="18" fill="#0d1117"/>
<text x="500" y="80" text-anchor="middle" fill="#8b949e" font-family="Arial, sans-serif" font-size="18">No commit activity found yet.</text>
</svg>"""

    items = sorted(counts.items(), reverse=True)
    total = sum(counts.values())
    active_days = len(items)
    first = items[-1][0]
    latest = items[0][0]
    max_count = max(counts.values())

    # Render the most recent 80 active dates as a readable table,
    # while keeping full-history totals in the header.
    visible = items[:80]
    row_h = 31
    header_h = 150
    height = header_h + row_h * len(visible) + 35
    width = 1000

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="1000" height="100%" rx="18" fill="#0d1117"/>',
        '<text x="40" y="42" fill="#f0f6fc" font-family="Arial, sans-serif" font-size="24" font-weight="700">GitHub Coding Journey</text>',
        f'<text x="40" y="72" fill="#8b949e" font-family="Arial, sans-serif" font-size="14">Full history · {total:,} commits · {active_days:,} active days · {repo_count} repositories</text>',
        f'<text x="40" y="96" fill="#8b949e" font-family="Arial, sans-serif" font-size="13">From {first} to {latest} · exact commit dates are calculated from GitHub commit history (UTC)</text>',
        '<line x1="40" y1="118" x2="960" y2="118" stroke="#30363d"/>',
        '<text x="55" y="140" fill="#8b949e" font-family="Arial, sans-serif" font-size="12" font-weight="700">DATE</text>',
        '<text x="260" y="140" fill="#8b949e" font-family="Arial, sans-serif" font-size="12" font-weight="700">COMMITS</text>',
        '<text x="350" y="140" fill="#8b949e" font-family="Arial, sans-serif" font-size="12" font-weight="700">ACTIVITY</text>',
    ]

    y = header_h
    for day, n in visible:
        bar = max(8, int(540 * n / max_count))
        svg += [
            f'<text x="55" y="{y+21}" fill="#c9d1d9" font-family="Arial, sans-serif" font-size="13">{escape(day)}</text>',
            f'<text x="260" y="{y+21}" fill="#f0f6fc" font-family="Arial, sans-serif" font-size="13" font-weight="700">{n}</text>',
            f'<rect x="350" y="{y+8}" width="{bar}" height="16" rx="8" fill="#00bcd4"/>',
            f'<text x="{365+bar}" y="{y+21}" fill="#8b949e" font-family="Arial, sans-serif" font-size="12">{n} commit{"s" if n != 1 else ""}</text>',
            f'<line x1="40" y1="{y+30}" x2="960" y2="{y+30}" stroke="#21262d"/>',
        ]
        y += row_h

    if len(items) > len(visible):
        svg.append(f'<text x="500" y="{y+12}" text-anchor="middle" fill="#8b949e" font-family="Arial, sans-serif" font-size="12">Showing latest {len(visible)} active dates · totals above include the complete GitHub history</text>')

    svg.append('</svg>')
    return "\n".join(svg)

def main():
    repos = all_repos()
    total_counts = Counter()

    for i, repo in enumerate(repos, 1):
        print(f"[{i}/{len(repos)}] {repo['name']}")
        total_counts.update(commits_for_repo(repo))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(make_svg(total_counts, len(repos)), encoding="utf-8")
    print(f"Wrote {OUT} with {sum(total_counts.values())} commits across {len(total_counts)} active dates.")

if __name__ == "__main__":
    main()
