"""
AtCoder platform fetcher.

Returns ONLY:
  - Contests currently running (live)
  - Contests starting within the next 14 days (upcoming)

Ended contests are NOT returned here; update_all.py handles
preserving recently-ended contests for up to 3 days.
"""

import requests
from datetime import datetime, timezone
from bs4 import BeautifulSoup

PLATFORM = "AtCoder"
FOURTEEN_DAYS_SEC = 14 * 24 * 3600


def fetch() -> list[dict]:
    """
    Fetch live and upcoming (within 14 days) contests from AtCoder.

    Returns a list of contest dicts with keys:
        platform, name, startTime (Unix timestamp), duration (seconds), url
    """
    contests = []
    headers = {"User-Agent": "Mozilla/5.0"}
    now = int(datetime.now(timezone.utc).timestamp())
    cutoff = now + FOURTEEN_DAYS_SEC
    seen: set[str] = set()

    try:
        url = "https://atcoder.jp/contests/"
        html = requests.get(url, headers=headers, timeout=10).text
        soup = BeautifulSoup(html, "html.parser")

        # contest-table-daily / contest-table-action hold upcoming contests
        # contest-table-recent holds recently running/ended ones shown on AtCoder's page
        for table_id in [
            "contest-table-recent",
            "contest-table-daily",
            "contest-table-action",
            "contest-table-upcoming",
        ]:
            table = soup.find("div", id=table_id)
            if not table:
                continue
            for row in table.find_all("tr")[1:]:
                cols = row.find_all("td")
                if len(cols) < 3:
                    continue

                name = cols[1].text.strip()
                link = "https://atcoder.jp" + cols[1].find("a")["href"]
                if link in seen:
                    continue
                seen.add(link)

                time_str = cols[0].text.strip()
                try:
                    dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S%z")
                except ValueError:
                    continue

                start = int(dt.timestamp())
                h, m = map(int, cols[2].text.strip().split(":"))
                duration = h * 3600 + m * 60
                end = start + duration

                # Keep only: currently running  OR  starts within the next 14 days
                is_running = start <= now < end
                is_upcoming = now < start <= cutoff
                if is_running or is_upcoming:
                    contests.append(
                        {
                            "platform": PLATFORM,
                            "name": name,
                            "startTime": start,
                            "duration": duration,
                            "url": link,
                        }
                    )

        print(f"[{PLATFORM}] Fetched {len(contests)} contests "
              f"(live + upcoming ≤14 days).")
    except Exception as exc:
        print(f"[{PLATFORM}] FAILED: {exc}")
        return []          # explicit empty list so callers can detect failure

    return contests