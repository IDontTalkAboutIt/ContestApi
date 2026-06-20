"""
LeetCode platform fetcher.

Returns ONLY:
  - Contests currently running (live)
  - Contests starting within the next 14 days (upcoming)

Ended contests are NOT returned here; update_all.py handles
preserving recently-ended contests for up to 3 days.

Note: The LeetCode GraphQL API returns ALL contests (including historical
ones), so we apply the same live/upcoming filter here.
"""

import requests
from datetime import datetime, timezone

PLATFORM = "LeetCode"
FOURTEEN_DAYS_SEC = 14 * 24 * 3600

GRAPHQL_QUERY = {
    "query": """
    query {
      allContests {
        title
        titleSlug
        startTime
        duration
      }
    }
    """
}


def fetch() -> list[dict]:
    """
    Fetch live and upcoming (within 14 days) contests from LeetCode.

    Returns a list of contest dicts with keys:
        platform, name, startTime (Unix timestamp), duration (seconds), url
    """
    contests = []
    headers = {"User-Agent": "Mozilla/5.0"}
    now = int(datetime.now(timezone.utc).timestamp())
    cutoff = now + FOURTEEN_DAYS_SEC

    try:
        resp = requests.post(
            "https://leetcode.com/graphql",
            json=GRAPHQL_QUERY,
            headers=headers,
            timeout=10,
        ).json()

        all_contests = resp.get("data", {}).get("allContests", [])

        for c in all_contests:
            start = c.get("startTime")
            duration = c.get("duration")
            if start is None or duration is None:
                continue

            end = start + duration
            is_running = start <= now < end
            is_upcoming = now < start <= cutoff
            if is_running or is_upcoming:
                contests.append(
                    {
                        "platform": PLATFORM,
                        "name": c["title"],
                        "startTime": start,
                        "duration": duration,
                        "url": f"https://leetcode.com/contest/{c['titleSlug']}",
                    }
                )

        print(f"[{PLATFORM}] Fetched {len(contests)} contests "
              f"(live + upcoming ≤14 days).")
    except Exception as exc:
        print(f"[{PLATFORM}] FAILED: {exc}")
        return []

    return contests