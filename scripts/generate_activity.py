#!/usr/bin/env python3
# Generates a GitHub-style contribution calendar with exact daily commit counts.

import os
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

USERNAME = os.getenv("GITHUB_USERNAME", "raheel-9deem")
TOKEN = os.getenv("GITHUB_TOKEN")
API = "https://api.github.com"

LEVELS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]


def get_json(path, params=None):
    import json
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "raheel-github-profile-calendar",
        },
    )
    if TOKEN:
        req.add_header("Authorization", "Bearer " + TOKEN)

    with urllib.request.urlopen(req, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))


def get_repositories():
    repositories = []
    page = 1

    while True:
        data = get_json(
            f"/users/{USERNAME}/repos",
            {"per_page": 100, "page": page, "type": "all", "sort": "full_name"},
        )
        if not data:
            break
        repositories.extend(data)
        if len(data) < 100:
            break
        page += 1

    return [
        repo for repo in repositories
        if not repo.get("fork") and not repo.get("archived")
    ]


def get_repo_commits(repo):
    owner = repo["owner"]["login"]
    name = repo["name"]
    counts = Counter()
    page = 1

    while True:
        try:
            data = get_json(
                f"/repos/{owner}/{name}/commits",
                {"author": USERNAME, "per_page": 100, "page": page},
            )
        except Exception as exc:
            print(f"Skipping {name}: {exc}")
            break

        if not data:
            break

        for item in data:
            commit = item.get("commit") or {}
            author = commit.get("author") or {}
            timestamp = author.get("date")
            if timestamp:
                counts[timestamp[:10]] += 1

        if len(data) < 100:
            break

        page += 1
        time.sleep(0.05)

    return counts


def sunday_start(day):
    return day - timedelta(days=(day.weekday() + 1) % 7)


def year_calendar(year):
    start = sunday_start(date(year, 1, 1))
    end = date(year, 12, 31)
    weeks = []
    cursor = start

    while cursor <= end:
        weeks.append([cursor + timedelta(days=i) for i in range(7)])
        cursor += timedelta(days=7)

    return weeks


def level_for_count(count, maximum):
    if count <= 0:
        return 0
    if maximum <= 1:
        return 4

    ratio = count / maximum
    if ratio <= 0.20:
        return 1
    if ratio <= 0.40:
        return 2
    if ratio <= 0.70:
        return 3
    return 4


def render_year(year, counts, maximum, x, y):
    cell = 14
    gap = 3
    step = cell + gap
    label_w = 32
    weeks = year_calendar(year)

    parts = [
        f'<g transform="translate({x},{y})">',
        f'<text x="0" y="16" fill="#f0f6fc" font-family="Arial,sans-serif" '
        f'font-size="14" font-weight="700">{year}</text>',
    ]

    month_positions = {}
    for index, week in enumerate(weeks):
        for current in week:
            if current.year == year and current.day <= 7:
                month_positions.setdefault(current.strftime("%b"), index)

    for month, column in month_positions.items():
        mx = label_w + column * step
        parts.append(
            f'<text x="{mx}" y="36" fill="#8b949e" font-family="Arial,sans-serif" '
            f'font-size="10">{month}</text>'
        )

    weekday_names = ["Sun", "", "Tue", "", "Thu", "", "Sat"]
    for row, label in enumerate(weekday_names):
        if label:
            ly = 51 + row * step + 10
            parts.append(
                f'<text x="0" y="{ly}" fill="#8b949e" '
                f'font-family="Arial,sans-serif" font-size="9">{label}</text>'
            )

    for col, week in enumerate(weeks):
        for row, current in enumerate(week):
            count = counts.get(current.isoformat(), 0)
            rx = label_w + col * step
            ry = 51 + row * step

            if current.year != year:
                fill = "#0d1117"
                stroke = "#0d1117"
            else:
                fill = LEVELS[level_for_count(count, maximum)]
                stroke = "#30363d"

            title = f"{current.isoformat()} — {count} commit{'s' if count != 1 else ''}"

            parts.append(
                f'<g><title>{escape(title)}</title>'
                f'<rect x="{rx}" y="{ry}" width="{cell}" height="{cell}" '
                f'rx="3" fill="{fill}" stroke="{stroke}" stroke-width="0.5"/>'
            )

            if count:
                label = "99+" if count > 99 else str(count)
                parts.append(
                    f'<text x="{rx + cell/2}" y="{ry + 10.5}" text-anchor="middle" '
                    f'fill="#f0f6fc" font-family="Arial,sans-serif" '
                    f'font-size="7" font-weight="700">{label}</text>'
                )

            parts.append("</g>")

    parts.append("</g>")
    return "\n".join(parts)


def make_calendar_svg(counts, repo_count):
    years = sorted({int(day[:4]) for day in counts}) or [datetime.utcnow().year]
    total = sum(counts.values())
    active_days = len(counts)
    first = min(counts) if counts else "—"
    latest = max(counts) if counts else "—"
    maximum = max(counts.values()) if counts else 1

    panel_h = 170
    header_h = 125
    footer_h = 58
    height = header_h + len(years) * panel_h + footer_h
    width = 1100

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" '
        f'height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" rx="18" fill="#0d1117"/>',
        '<text x="32" y="40" fill="#f0f6fc" font-family="Arial,sans-serif" '
        'font-size="24" font-weight="700">GitHub Activity</text>',
        '<line x1="32" y1="57" x2="1068" y2="57" stroke="#30363d"/>',
        f'<text x="32" y="82" fill="#8b949e" font-family="Arial,sans-serif" '
        f'font-size="12">Full history · exact daily commit counts · '
        f'{total:,} total commits · {active_days:,} active days</text>',
        f'<text x="32" y="102" fill="#8b949e" font-family="Arial,sans-serif" '
        f'font-size="11">From {first} to {latest} · {repo_count} non-fork repositories · UTC commit dates</text>',
    ]

    current_y = header_h
    for year in years:
        parts.append(render_year(year, counts, maximum, 32, current_y))
        current_y += panel_h

    legend_y = current_y - 20
    parts.append(
        f'<text x="32" y="{legend_y}" fill="#8b949e" '
        f'font-family="Arial,sans-serif" font-size="10">Less</text>'
    )

    lx = 62
    for index, color in enumerate(LEVELS):
        parts.append(
            f'<rect x="{lx + index*22}" y="{legend_y-11}" width="14" height="14" '
            f'rx="3" fill="{color}" stroke="#30363d" stroke-width=".5"/>'
        )

    parts.append(
        f'<text x="{lx + len(LEVELS)*22 + 8}" y="{legend_y}" fill="#8b949e" '
        f'font-family="Arial,sans-serif" font-size="10">More</text>'
    )
    parts.append(
        f'<text x="1068" y="{legend_y}" text-anchor="end" fill="#6e7681" '
        f'font-family="Arial,sans-serif" font-size="9">Generated by GitHub Actions</text>'
    )
    parts.append("</svg>")

    return "\n".join(parts)


def make_overview_svg():
    user = get_json(f"/users/{USERNAME}")
    repos = user.get("public_repos", 0)
    followers = user.get("followers", 0)
    following = user.get("following", 0)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="155" viewBox="0 0 1000 155">
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
</svg>"""


def main():
    repositories = get_repositories()
    all_counts = Counter()

    print(f"Found {len(repositories)} non-fork, non-archived repositories.")

    for index, repo in enumerate(repositories, start=1):
        print(f"[{index}/{len(repositories)}] {repo['name']}")
        all_counts.update(get_repo_commits(repo))

    output_dir = Path("assets")
    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "github-contributions.svg").write_text(
        make_calendar_svg(all_counts, len(repositories)),
        encoding="utf-8",
    )

    (output_dir / "github-overview.svg").write_text(
        make_overview_svg(),
        encoding="utf-8",
    )

    print(
        f"Generated {sum(all_counts.values()):,} commits across "
        f"{len(all_counts):,} active dates."
    )


if __name__ == "__main__":
    main()
