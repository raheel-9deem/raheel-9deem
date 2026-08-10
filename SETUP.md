# GitHub Profile Auto-Update

1. Replace the files in your profile repository with this package.
2. Push to `main`.
3. Open **Actions → Update GitHub Profile Data**.
4. Click **Run workflow** once manually.
5. After that, GitHub Actions checks every 30 minutes.

The calendar is always a rolling 365-day window.

Important: GitHub scheduled workflows are not guaranteed to start at the exact
minute during platform load. `*/30 * * * *` means GitHub schedules the check
every 30 minutes; a small delay can occasionally happen.

The workflow does NOT create a commit when nothing changed. If no new commits
or profile data changes occurred, the existing SVG remains the same.
