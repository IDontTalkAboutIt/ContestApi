"""
CodeChef platform fetcher.

Returns ONLY:
  - Contests currently running (live)
  - Contests starting within the next 14 days (upcoming)

Ended contests are NOT returned here; update_all.py handles
preserving recently-ended contests for up to 3 days.
"""

import requests
from datetime import datetime, timezone

PLATFORM = "CodeChef"
FOURTEEN_DAYS_SEC = 14 * 24 * 3600


def fetch() -> list[dict]:
    """
    Fetch live and upcoming (within 14 days) contests from CodeChef.

    Returns a list of contest dicts with keys:
        platform, name, startTime (Unix timestamp), duration (seconds), url
    """
    contests = []
    headers = {"User-Agent": "Mozilla/5.0"}
    now = int(datetime.now(timezone.utc).timestamp())
    cutoff = now + FOURTEEN_DAYS_SEC

    try:
        data = requests.get(
            "https://www.codechef.com/api/list/contests/all",
            headers=headers,
            timeout=10,
        ).json()

        # present_contests = running now; future_contests = upcoming
        # We intentionally skip past_contests — update_all.py preserves recents.
        relevant_buckets = (
            data.get("present_contests", [])
            + data.get("future_contests", [])
        )

        for c in relevant_buckets:
            try:
                dt = datetime.fromisoformat(c["contest_start_date_iso"])
            except (KeyError, ValueError):
                continue

            start = int(dt.timestamp())
            duration = int(c.get("contest_duration", 0)) * 60
            end = start + duration

            is_running = start <= now < end
            is_upcoming = now < start <= cutoff
            if is_running or is_upcoming:
                contests.append(
                    {
                        "platform": PLATFORM,
                        "name": c["contest_name"],
                        "startTime": start,
                        "duration": duration,
                        "url": f"https://www.codechef.com/{c['contest_code']}",
                    }
                )

        print(f"[{PLATFORM}] Fetched {len(contests)} contests "
              f"(live + upcoming ≤14 days).")
    except Exception as exc:
        print(f"[{PLATFORM}] FAILED: {exc}")
        return []

    return contests