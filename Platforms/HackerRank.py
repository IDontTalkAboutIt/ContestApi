"""
HackerRank platform fetcher.

Returns ONLY:
  - Contests currently running (live)
  - Contests starting within the next 14 days (upcoming)

Ended contests are NOT returned here; update_all.py handles
preserving recently-ended contests for up to 3 days.
"""

import requests
from datetime import datetime, timezone

PLATFORM = "HackerRank"
FOURTEEN_DAYS_SEC = 14 * 24 * 3600

# Contests to always skip (permanent / non-competitive events)
SKIP_NAMES = {"ProjectEuler+"}


def fetch() -> list[dict]:
    """
    Fetch live and upcoming (within 14 days) contests from HackerRank.

    Returns a list of contest dicts with keys:
        platform, name, startTime (Unix timestamp), duration (seconds), url
    """
    contests = []
    headers = {"User-Agent": "Mozilla/5.0"}
    now = int(datetime.now(timezone.utc).timestamp())
    cutoff = now + FOURTEEN_DAYS_SEC

    try:
        resp = requests.get(
            "https://www.hackerrank.com/rest/contests/upcoming",
            headers=headers,
            timeout=10,
        ).json()

        for c in resp.get("models", []):
            if c.get("name") in SKIP_NAMES:
                continue

            start = c.get("epoch_starttime")
            end = c.get("epoch_endtime")
            if start is None or end is None:
                continue

            duration = end - start
            is_running = start <= now < end
            is_upcoming = now < start <= cutoff
            if is_running or is_upcoming:
                contests.append(
                    {
                        "platform": PLATFORM,
                        "name": c["name"],
                        "startTime": start,
                        "duration": duration,
                        "url": f"https://www.hackerrank.com/contests/{c['slug']}/challenges",
                    }
                )

        print(f"[{PLATFORM}] Fetched {len(contests)} contests "
              f"(live + upcoming ≤14 days).")
    except Exception as exc:
        print(f"[{PLATFORM}] FAILED: {exc}")
        return []

    return contests