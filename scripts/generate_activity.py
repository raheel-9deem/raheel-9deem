#!/usr/bin/env python3
import json, os, time, urllib.parse, urllib.request
from collections import Counter
from pathlib import Path

USERNAME = os.getenv("GITHUB_USERNAME", "raheel-9deem")
TOKEN = os.getenv("GITHUB_TOKEN")
API = "https://api.github.com"

def get(path, params=None):
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "raheel-github-profile"
    })
    if TOKEN:
        req.add_header("Authorization", "Bearer " + TOKEN)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def get_repos():
    repos, page = [], 1
    while True:
        data = get(f"/users/{USERNAME}/repos", {"per_page": 100, "page": page, "type": "all"})
        if not data:
            break
        repos.extend(data)
        if len(data) < 100:
            break
        page += 1
    return [r for r in repos if not r.get("fork") and not r.get("archived")]

def get_commits(repo):
    owner, name = repo["owner"]["login"], repo["name"]
    counts, page = Counter(), 1
    while True:
        data = get(f"/repos/{owner}/{name}/commits", {"author": USERNAME, "per_page": 100, "page": page})
        if not data:
            break
        for item in data:
            date = ((item.get("commit") or {}).get("author") or {}).get("date")
            if date:
                counts[date[:10]] += 1
        if len(data) < 100:
            break
        page += 1
        time.sleep(.05)
    return counts

def make_activity(counts, repo_count):
    items = sorted(counts.items(), reverse=True)
    total = sum(counts.values())
    days = len(items)
    first = items[-1][0] if items else "—"
    latest = items[0][0] if items else "—"
    max_n = max(counts.values()) if counts else 1
    visible = items[:90]
    row_h, top = 30, 145
    height = top + max(1, len(visible))*row_h + 45
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="{height}" viewBox="0 0 1000 {height}">',
           '<rect width="100%" height="100%" rx="18" fill="#0d1117"/>',
           '<text x="36" y="40" fill="#f0f6fc" font-family="Arial,sans-serif" font-size="23" font-weight="700">GitHub Coding Journey</text>',
           f'<text x="36" y="69" fill="#8b949e" font-family="Arial,sans-serif" font-size="13">Full history · {total:,} commits · {days:,} active days · {repo_count} non-fork repositories</text>',
           f'<text x="36" y="91" fill="#8b949e" font-family="Arial,sans-serif" font-size="12">First: {first} · Latest: {latest} · grouped by commit date (UTC)</text>',
           '<line x1="36" y1="111" x2="964" y2="111" stroke="#30363d"/>',
           '<text x="50" y="134" fill="#8b949e" font-family="Arial,sans-serif" font-size="11" font-weight="700">DATE</text>',
           '<text x="220" y="134" fill="#8b949e" font-family="Arial,sans-serif" font-size="11" font-weight="700">COMMITS</text>',
           '<text x="315" y="134" fill="#8b949e" font-family="Arial,sans-serif" font-size="11" font-weight="700">ACTIVITY</text>']
    y = top
    for date, n in visible:
        bar = max(8, int(560*n/max_n))
        out += [f'<text x="50" y="{y+19}" fill="#c9d1d9" font-family="Arial,sans-serif" font-size="12">{date}</text>',
                f'<text x="220" y="{y+19}" fill="#f0f6fc" font-family="Arial,sans-serif" font-size="12" font-weight="700">{n}</text>',
                f'<rect x="315" y="{y+6}" width="{bar}" height="15" rx="7" fill="#00bcd4"/>',
                f'<text x="{min(900,330+bar)}" y="{y+19}" fill="#8b949e" font-family="Arial,sans-serif" font-size="11">{n} commit{"s" if n != 1 else ""}</text>',
                f'<line x1="36" y1="{y+28}" x2="964" y2="{y+28}" stroke="#21262d"/>']
        y += row_h
    if len(items) > len(visible):
        out.append(f'<text x="500" y="{y+18}" text-anchor="middle" fill="#8b949e" font-family="Arial,sans-serif" font-size="11">Latest {len(visible)} active dates shown · totals include complete history</text>')
    out.append('</svg>')
    return "\n".join(out)

def make_overview():
    user = get(f"/users/{USERNAME}")
    repos = user.get("public_repos", 0)
    followers = user.get("followers", 0)
    following = user.get("following", 0)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="155" viewBox="0 0 1000 155">
<rect width="1000" height="155" rx="18" fill="#0d1117"/>
<text x="36" y="38" fill="#f0f6fc" font-family="Arial,sans-serif" font-size="23" font-weight="700">GitHub Overview</text>
<line x1="36" y1="57" x2="964" y2="57" stroke="#30363d"/>
<text x="110" y="91" fill="#00bcd4" font-family="Arial,sans-serif" font-size="25" font-weight="700">{repos}</text>
<text x="110" y="116" fill="#8b949e" font-family="Arial,sans-serif" font-size="12">Public repositories</text>
<text x="400" y="91" fill="#00bcd4" font-family="Arial,sans-serif" font-size="25" font-weight="700">{followers}</text>
<text x="400" y="116" fill="#8b949e" font-family="Arial,sans-serif" font-size="12">Followers</text>
<text x="690" y="91" fill="#00bcd4" font-family="Arial,sans-serif" font-size="25" font-weight="700">{following}</text>
<text x="690" y="116" fill="#8b949e" font-family="Arial,sans-serif" font-size="12">Following</text>
<text x="500" y="145" text-anchor="middle" fill="#6e7681" font-family="Arial,sans-serif" font-size="10">Generated automatically by GitHub Actions.</text>
</svg>'''

def main():
    repos = get_repos()
    counts = Counter()
    for repo in repos:
        try:
            counts.update(get_commits(repo))
        except Exception as exc:
            print("Skipping", repo.get("name"), exc)
    Path("assets/github-activity.svg").write_text(make_activity(counts, len(repos)), encoding="utf-8")
    Path("assets/github-overview.svg").write_text(make_overview(), encoding="utf-8")

if __name__ == "__main__":
    main()
