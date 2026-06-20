# contest-api

A Python-based contest aggregator that fetches live and upcoming competitive programming contests from multiple platforms, merges them into a single unified JSON file (`AllContest.json`), and keeps that file up to date over time.

---

## What it does

Running `update_all.py` performs the following in sequence:

1. **Loads** the existing `AllContest.json` as a persistent store.
2. **Fetches** fresh contest data from every supported platform.
3. **Merges** new and updated contests into the store (using the contest URL as the unique key).
4. **Preserves** recently-ended contests for a 3-day grace period.
5. **Evicts** contests that ended more than 3 days ago.
6. **Deduplicates** by URL.
7. **Sorts** results: running → future (soonest first) → recent (most-recently-ended first).
8. **Saves** the final list back to `AllContest.json`.

---

## Project structure

```
contest-api/
├── update_all.py          # Entry point — orchestrates all fetchers and writes AllContest.json
├── AllContest.json        # Output file — the merged, filtered, sorted contest list
├── requirements.txt       # Python dependencies
├── Platforms/             # One fetcher module per platform
│   ├── AtCoder.py
│   ├── CodeChef.py
│   ├── CodeForces.py
│   ├── HackerRank.py
│   └── LeetCode.py
└── Logos/                 # SVG logo data for each platform (JSON format)
    ├── AtCoder.json
    ├── CodeChef.json
    ├── CodeForces.json
    ├── HackerRank.json
    ├── LeetCode.json
    └── TopCoder.json
```

---

## Output format

`AllContest.json` is a JSON array. Each entry has the following fields:

| Field       | Type    | Description                                      |
|-------------|---------|--------------------------------------------------|
| `platform`  | string  | Platform name (e.g. `"CodeForces"`)              |
| `name`      | string  | Contest name                                     |
| `startTime` | integer | Unix timestamp (UTC) of the contest start        |
| `duration`  | integer | Contest length in seconds                        |
| `url`       | string  | Direct link to the contest page                  |
| `status`    | string  | One of `"running"`, `"future"`, or `"recent"`    |

**Status values:**
- `running` — contest has started but not yet ended
- `future` — contest has not started yet (within the next 14 days)
- `recent` — contest ended within the last 3 days (grace period; dropped after)

**Example entry:**
```json
{
  "platform": "CodeForces",
  "name": "Codeforces Round 1098 (Div. 2)",
  "startTime": 1778942100,
  "duration": 8100,
  "url": "https://codeforces.com/contestRegistration/2228",
  "status": "future"
}
```

---

## Supported platforms

| Platform    | Data source                  | Method          |
|-------------|------------------------------|-----------------|
| AtCoder     | `atcoder.jp/contests/`       | HTML scraping   |
| CodeChef    | `codechef.com/api/list/contests/all` | REST API |
| CodeForces  | `codeforces.com/api/contest.list`    | REST API |
| HackerRank  | `hackerrank.com/rest/contests/upcoming` | REST API |
| LeetCode    | `leetcode.com/graphql`       | GraphQL API     |

Each fetcher returns only **currently running** contests and contests **starting within the next 14 days**. Historical data is intentionally excluded at the fetcher level; `update_all.py` handles retention of recently-ended contests separately.

---

## How each platform fetcher works

### AtCoder (`Platforms/AtCoder.py`)
Scrapes the AtCoder contests page with `requests` and `BeautifulSoup`. It looks for four specific HTML `<div>` sections by ID (`contest-table-recent`, `contest-table-daily`, `contest-table-action`, `contest-table-upcoming`) and parses contest name, start time, and duration from each table row. A `seen` set prevents duplicate URLs across sections.

### CodeChef (`Platforms/CodeChef.py`)
Calls the CodeChef REST API and reads two keys from the response: `present_contests` (currently running) and `future_contests` (upcoming). Duration is given in minutes by the API and converted to seconds.

### CodeForces (`Platforms/CodeForces.py`)
Calls the Codeforces `contest.list` REST API, which returns all contests including historical ones. The fetcher filters to only those that are currently running or start within 14 days. Start time and duration are provided directly as Unix seconds.

### HackerRank (`Platforms/HackerRank.py`)
Calls the HackerRank upcoming contests REST endpoint. A hardcoded `SKIP_NAMES` set filters out permanent/non-competitive events (e.g. `ProjectEuler+`). Duration is derived as `epoch_endtime − epoch_starttime`.

### LeetCode (`Platforms/LeetCode.py`)
Calls the LeetCode GraphQL API with a query for `allContests` (which returns all contests including historical). The same running/upcoming filter is applied. The contest URL is built from the `titleSlug` field.

---

## Merge and retention logic

`update_all.py` uses the contest **URL as the deduplication key** across all operations.

**On each run:**
- Fresh contests from a successful fetch are **upserted** (added if new, updated if existing).
- If a platform fetch succeeds but no longer returns a URL that was previously stored, that entry is **kept only if it is in the 3-day recent grace period**, then dropped.
- If a platform fetch **fails** (network error, API error, parse error), all existing entries for that platform are **kept untouched** to avoid data loss on a transient error.
- After all merges, every entry is re-evaluated: contests older than 3 days are **dropped**, all others get their `status` recalculated from the current time.

This means `AllContest.json` always reflects the current state of contests, with a soft landing for very recently ended ones.

---

## Logos

The `Logos/` directory contains one JSON file per platform. Each file holds:

```json
{
  "platform": "CodeForces",
  "svg": "<svg ...>...</svg>",
  "tint": false
}
```

The `svg` field is an inline SVG string ready to embed in a frontend. The `tint` boolean indicates whether the SVG should be tinted (useful for monochrome logos). These files are static assets used by downstream consumers of this API (e.g. a frontend app) and are not updated by `update_all.py`.

---

## Setup

**Requirements:** Python 3.10+

```bash
pip install -r requirements.txt
```

`requirements.txt` contains:
```
requests
beautifulsoup4
```

---

## Running

```bash
python update_all.py
```

On completion, the script prints a summary:

```
Loaded 42 contests from AllContest.json.
[AtCoder] Fetched 8 contests (live + upcoming ≤14 days).
[CodeChef] Fetched 3 contests (live + upcoming ≤14 days).
[CodeForces] Fetched 5 contests (live + upcoming ≤14 days).
[HackerRank] Fetched 2 contests (live + upcoming ≤14 days).
[LeetCode] Fetched 2 contests (live + upcoming ≤14 days).

AllContest.json updated — 44 contest(s) kept.
  Running : 1
  Future  : 40  (within next 14 days)
  Recent  : 3   (ended within last 3 days)
```

To keep `AllContest.json` fresh, run this script on a schedule — for example as a GitHub Actions workflow, a cron job, or any CI/CD pipeline that commits the updated file back to the repository.

---

## Adding a new platform

1. Create `Platforms/<PlatformName>.py`.
2. Implement a `fetch() -> list[dict]` function that returns a list of contest dicts with keys: `platform`, `name`, `startTime` (Unix timestamp), `duration` (seconds), `url`.
3. Return only **running or upcoming (≤14 days)** contests. Return `[]` on any error (after printing a message).
4. Import and register the fetcher in `update_all.py`'s `PLATFORMS` dict.
5. Optionally add a logo JSON to `Logos/`.
