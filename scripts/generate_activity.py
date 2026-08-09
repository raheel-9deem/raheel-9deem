#!/usr/bin/env python3
# Generates a rolling 365-day GitHub-style contribution calendar.
# Every run recalculates the window as today + previous 364 days.

import os
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

USERNAME = os.getenv("GITHUB_USERNAME", "raheel-9deem")
TOKEN = os.getenv("GITHUB_TOKEN")
API = "https://api.github.com"

LEVELS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
WINDOW_DAYS = 365


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
            {
                "per_page": 100,
                "page": page,
                "type": "all",
                "sort": "full_name",
            },
        )

        if not data:
            break

        repositories.extend(data)

        if len(data) < 100:
            break

        page += 1

    # Count only the user's own, non-archived repositories.
    return [
        repo
        for repo in repositories
        if not repo.get("fork") and not repo.get("archived")
    ]


def get_repo_commits(repo, since_iso, until_iso):
    owner = repo["owner"]["login"]
    name = repo["name"]
    counts = Counter()
    page = 1

    while True:
        try:
            data = get_json(
                f"/repos/{owner}/{name}/commits",
                {
                    "author": USERNAME,
                    "since": since_iso,
                    "until": until_iso,
                    "per_page": 100,
                    "page": page,
                },
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


def sunday_start(day):
    return day - timedelta(days=(day.weekday() + 1) % 7)


def build_calendar_days(start_day, end_day):
    # The visible grid begins on Sunday so the calendar looks like GitHub.
    grid_start = sunday_start(start_day)

    # Extend to Saturday so every week is complete.
    days = []
    cursor = grid_start

    while cursor <= end_day or cursor.weekday() != 5:
        days.append(cursor)
        cursor += timedelta(days=1)

        if cursor > end_day and cursor.weekday() == 6:
            # We already have a complete final Saturday.
            break

    return days


def month_label_positions(days):
    positions = {}

    for index, current in enumerate(days):
        # Label the first day of each month that appears in the 365-day window.
        if current.day == 1:
            positions[current.strftime("%b")] = index

    return positions


def make_calendar_svg(counts, start_day, end_day, repo_count):
    days = build_calendar_days(start_day, end_day)

    # Convert days into Sunday-Saturday columns.
    weeks = []
    for i in range(0, len(days), 7):
        weeks.append(days[i:i + 7])

    maximum = max(counts.values()) if counts else 1
    total = sum(counts.values())
    active_days = sum(1 for d in counts if start_day.isoformat() <= d <= end_day.isoformat())

    # Header + calendar + footer.
    cell = 16
    gap = 4
    step = cell + gap
    left = 38
    weekday_width = 32
    top = 108
    row_height = 7 * step
    calendar_width = weekday_width + len(weeks) * step
    width = max(1050, left * 2 + calendar_width)
    height = top + row_height + 95

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" '
        f'height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" rx="18" fill="#0d1117"/>',

        '<text x="32" y="38" fill="#f0f6fc" font-family="Arial,sans-serif" '
        'font-size="24" font-weight="700">GitHub Activity</text>',

        '<line x1="32" y1="57" x2="' + str(width - 32) +
        '" y2="57" stroke="#30363d"/>',

        f'<text x="32" y="80" fill="#8b949e" font-family="Arial,sans-serif" '
        f'font-size="12">Rolling last 365 days · {total:,} commits · '
        f'{active_days:,} active days</text>',

        f'<text x="32" y="98" fill="#8b949e" font-family="Arial,sans-serif" '
        f'font-size="11">{start_day.isoformat()} → {end_day.isoformat()} · '
        f'{repo_count} non-fork repositories · UTC commit dates</text>',
    ]

    # Month labels.
    for month, index in month_label_positions(days).items():
        col = index // 7
        x = left + weekday_width + col * step
        parts.append(
            f'<text x="{x}" y="120" fill="#8b949e" '
            f'font-family="Arial,sans-serif" font-size="10">{month}</text>'
        )

    # Weekday labels.
    weekday_names = ["Sun", "", "Tue", "", "Thu", "", "Sat"]
    for row, label in enumerate(weekday_names):
        if label:
            y = top + row * step + 12
            parts.append(
                f'<text x="{left}" y="{y}" fill="#8b949e" '
                f'font-family="Arial,sans-serif" font-size="9">{label}</text>'
            )

    # Contribution squares.
    for col, week in enumerate(weeks):
        for row, current in enumerate(week):
            inside_window = start_day <= current <= end_day
            date_key = current.isoformat()
            count = counts.get(date_key, 0) if inside_window else 0

            x = left + weekday_width + col * step
            y = top + row * step

            if not inside_window:
                fill = "#0d1117"
                stroke = "#0d1117"
            else:
                fill = LEVELS[level_for_count(count, maximum)]
                stroke = "#30363d"

            title = (
                f"{date_key} — {count} "
                f"commit{'s' if count != 1 else ''}"
                if inside_window
                else f"{date_key} — outside 365-day window"
            )

            parts.append(
                f'<g><title>{escape(title)}</title>'
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" '
                f'rx="3" fill="{fill}" stroke="{stroke}" stroke-width="0.5"/>'
            )

            # Exact count inside every active day.
            if inside_window and count:
                label = "99+" if count > 99 else str(count)
                parts.append(
                    f'<text x="{x + cell / 2}" y="{y + 11.5}" '
                    f'text-anchor="middle" fill="#f0f6fc" '
                    f'font-family="Arial,sans-serif" font-size="8" '
                    f'font-weight="700">{label}</text>'
                )

            parts.append("</g>")

    footer_y = top + row_height + 24

    parts.append(
        f'<text x="{left}" y="{footer_y}" fill="#8b949e" '
        f'font-family="Arial,sans-serif" font-size="10">Less</text>'
    )

    legend_x = left + 30

    for index, color in enumerate(LEVELS):
        parts.append(
            f'<rect x="{legend_x + index * 23}" y="{footer_y - 11}" '
            f'width="15" height="15" rx="3" fill="{color}" '
            f'stroke="#30363d" stroke-width=".5"/>'
        )

    parts.append(
        f'<text x="{legend_x + len(LEVELS) * 23 + 8}" y="{footer_y}" '
        f'fill="#8b949e" font-family="Arial,sans-serif" '
        f'font-size="10">More</text>'
    )

    parts.append(
        f'<text x="{width - 32}" y="{footer_y}" text-anchor="end" '
        f'fill="#6e7681" font-family="Arial,sans-serif" '
        f'font-size="9">Automatically updated daily · oldest date drops off as a new day arrives</text>'
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
    # Use UTC so the rolling window is deterministic and matches GitHub commit dates.
    today = datetime.now(timezone.utc).date()

    # Exactly 365 dates: today + previous 364 calendar days.
    start_day = today - timedelta(days=WINDOW_DAYS - 1)

    # GitHub API accepts ISO-8601 timestamps.
    since_iso = f"{start_day.isoformat()}T00:00:00Z"
    until_iso = f"{today.isoformat()}T23:59:59Z"

    print(f"Rolling window: {start_day} -> {today} ({WINDOW_DAYS} days)")

    repositories = get_repositories()
    all_counts = Counter()

    print(f"Found {len(repositories)} non-fork, non-archived repositories.")

    for index, repo in enumerate(repositories, start=1):
        print(f"[{index}/{len(repositories)}] {repo['name']}")
        all_counts.update(get_repo_commits(repo, since_iso, until_iso))

    # Keep only dates inside the exact rolling window.
    filtered = Counter(
        {
            day: count
            for day, count in all_counts.items()
            if start_day.isoformat() <= day <= today.isoformat()
        }
    )

    output_dir = Path("assets")
    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "github-contributions.svg").write_text(
        make_calendar_svg(filtered, start_day, today, len(repositories)),
        encoding="utf-8",
    )

    (output_dir / "github-overview.svg").write_text(
        make_overview_svg(),
        encoding="utf-8",
    )

    print(
        f"Generated rolling 365-day calendar: "
        f"{sum(filtered.values()):,} commits across {len(filtered):,} active dates."
    )


if __name__ == "__main__":
    main()
