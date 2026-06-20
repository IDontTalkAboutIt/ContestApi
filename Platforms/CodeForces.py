"""
CodeForces platform fetcher.

Returns ONLY:
  - Contests currently running (live)
  - Contests starting within the next 14 days (upcoming)

Ended contests are NOT returned here; update_all.py handles
preserving recently-ended contests for up to 3 days.
"""

import requests
from datetime import datetime, timezone

PLATFORM = "CodeForces"
FOURTEEN_DAYS_SEC = 14 * 24 * 3600


def fetch() -> list[dict]:
    """
    Fetch live and upcoming (within 14 days) contests from Codeforces.

    Returns a list of contest dicts with keys:
        platform, name, startTime (Unix timestamp), duration (seconds), url
    """
    contests = []
    headers = {"User-Agent": "Mozilla/5.0"}
    now = int(datetime.now(timezone.utc).timestamp())
    cutoff = now + FOURTEEN_DAYS_SEC

    try:
        resp = requests.get(
            "https://codeforces.com/api/contest.list",
            headers=headers,
            timeout=10,
        ).json()

        if resp.get("status") != "OK":
            raise ValueError(f"API returned non-OK status: {resp.get('comment', '')}")

        for c in resp.get("result", []):
            start = c.get("startTimeSeconds")
            duration = c.get("durationSeconds")
            if start is None or duration is None:
                continue

            end = start + duration
            is_running = start <= now < end
            is_upcoming = now < start <= cutoff
            if is_running or is_upcoming:
                contests.append(
                    {
                        "platform": PLATFORM,
                        "name": c["name"],
                        "startTime": start,
                        "duration": duration,
                        "url": f"https://codeforces.com/contestRegistration/{c['id']}",
                    }
                )

        print(f"[{PLATFORM}] Fetched {len(contests)} contests "
              f"(live + upcoming ≤14 days).")
    except Exception as exc:
        print(f"[{PLATFORM}] FAILED: {exc}")
        return []

    return contests