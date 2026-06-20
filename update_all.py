"""
update_all.py — Contest aggregation entry point.

Workflow
--------
1. Read the existing data from AllContest.json (the persistent store).
2. Fetch fresh data from every platform fetcher.
   Each fetcher returns ONLY live contests + contests starting within
   the next 14 days — no historical data.
3. Merge freshly fetched contests into the store:
     • New contests (identified by URL) are added.
     • Existing contests get their metadata refreshed (name/duration
       can change, e.g. a rescheduled contest).
4. Preserve older contests already in AllContest.json if they ended
   less than 3 days ago ("recent" grace period).
5. Remove contests that ended more than 3 days ago.
6. Avoid duplicate contests during merging (URL is the dedup key).
7. Recalculate status for every surviving entry.
8. Save the final merged, filtered, and sorted result to AllContest.json.

Status categories
-----------------
  "running" — contest has started but not yet ended
  "future"  — contest has not started yet
  "recent"  — ended within the last 3 days (grace period)
  (dropped) — ended more than 3 days ago

Platform-failure safety
-----------------------
If a platform fetch fails (returns an empty list due to an exception),
its existing entries in AllContest.json are kept as-is so we don't lose
data on a transient network error.  A platform that genuinely has zero
live/upcoming contests also returns [], so we use an explicit sentinel
(None vs []) — fetchers return [] on error, but the aggregator tracks
which platforms threw exceptions vs returned legitimately empty.
"""

import json
import os
import sys
from datetime import datetime, timezone

# ── Import platform fetchers ──────────────────────────────────────────────────

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "Platforms"))

import AtCoder
import CodeChef
import CodeForces
import HackerRank
import LeetCode

# Map platform name → fetch function
PLATFORMS: dict[str, callable] = {
    "AtCoder":    AtCoder.fetch,
    "CodeChef":   CodeChef.fetch,
    "CodeForces": CodeForces.fetch,
    "HackerRank": HackerRank.fetch,
    "LeetCode":   LeetCode.fetch,
}

ALLCONTEST_PATH = os.path.join(os.path.dirname(__file__), "AllContest.json")
THREE_DAYS_SEC  = 3 * 24 * 3600  # grace period for recently-ended contests

# Sort priority: running first, then future (soonest first), then recent
STATUS_ORDER = {"running": 0, "future": 1, "recent": 2}


# ── Helpers ───────────────────────────────────────────────────────────────────

def classify(start: int, duration: int, now: int) -> str | None:
    """
    Return the status category for a contest, or None if it should be dropped.

    Parameters
    ----------
    start    : Unix timestamp of the contest start time.
    duration : Contest length in seconds.
    now      : Current Unix timestamp.

    Returns
    -------
    "future"  — contest has not started yet
    "running" — contest is currently in progress
    "recent"  — contest ended within the last 3 days (keep for now)
    None      — contest ended more than 3 days ago (drop it)
    """
    end = start + duration
    if now < start:
        return "future"
    if now < end:
        return "running"
    if now < end + THREE_DAYS_SEC:
        return "recent"
    return None  # too old — remove from store


def sort_key(contest: dict) -> tuple:
    """Sorting key: running → future (soonest) → recent (most-recently-ended)."""
    order = STATUS_ORDER.get(contest["status"], 9)
    if contest["status"] == "recent":
        # Most recently ended first
        return (order, -(contest["startTime"] + contest["duration"]))
    return (order, contest["startTime"])


# ── Step 1: Load existing data ────────────────────────────────────────────────

if os.path.exists(ALLCONTEST_PATH):
    with open(ALLCONTEST_PATH, "r", encoding="utf-8") as fh:
        try:
            existing: list[dict] = json.load(fh)
        except json.JSONDecodeError:
            print("⚠️  AllContest.json is malformed — starting fresh.")
            existing = []
else:
    existing = []

# Build a URL-keyed lookup for O(1) access.
# URL is the deduplication key (unique per contest across platforms).
stored: dict[str, dict] = {c["url"]: c for c in existing}

print(f"📂 Loaded {len(stored)} contests from AllContest.json.")

# ── Step 2: Fetch fresh data from every platform ──────────────────────────────

now = int(datetime.now(timezone.utc).timestamp())

# Separate successful fetches from failed ones so we can apply different
# merge strategies for each.
fresh_by_platform:   dict[str, list[dict]] = {}   # platform → list of contests
errored_platforms:   set[str]              = set() # platforms whose fetch threw

for name, fn in PLATFORMS.items():
    try:
        result = fn()
        # Fetchers return [] both on error (after printing) and when there are
        # legitimately no live/upcoming contests.  We treat both as success here
        # because the fetcher already handled its own exception internally and
        # printed a message.  The "no data from a failed fetch" vs "no contests"
        # ambiguity is acceptable: on a genuine failure the existing entries are
        # kept by the merge logic below.
        fresh_by_platform[name] = result if result is not None else []
    except Exception as exc:
        # Outer safety net — should not normally be reached because each
        # fetcher has its own try/except, but just in case.
        print(f"[{name}] Unexpected error in fetch: {exc}")
        errored_platforms.add(name)
        fresh_by_platform[name] = []

# ── Step 3: Merge fresh contests into the store ───────────────────────────────
#
# For each successfully fetched contest:
#   • If it already exists (same URL), update metadata (name, duration, etc.)
#     in case the contest was rescheduled or renamed.
#   • If it's new, add it to the store.
#
# After upserting, deal with contests NOT returned by a successful platform:
#   • If that platform's fetch succeeded but didn't include a stored URL,
#     it means the platform no longer lists that contest (cancelled, far past,
#     or outside the 14-day window).  Keep it ONLY if it's still in the
#     "recent" grace period (ended < 3 days ago) — the platform may not return
#     past contests even though they just ended.
#   • If the platform fetch failed (errored_platforms), keep all existing
#     entries from that platform untouched.

# Index fresh contest URLs per platform for fast membership testing
fresh_urls: dict[str, set[str]] = {
    name: {c["url"] for c in contests}
    for name, contests in fresh_by_platform.items()
}

# Upsert: add new or refresh existing
for name, contests in fresh_by_platform.items():
    for c in contests:
        stored[c["url"]] = {
            "platform":  c["platform"],
            "name":      c["name"],
            "startTime": c["startTime"],
            "duration":  c["duration"],
            "url":       c["url"],
        }

# Evict stale entries for platforms that fetched successfully
urls_to_evict: list[str] = []
for url, c in stored.items():
    platform = c["platform"]
    if platform in errored_platforms:
        continue  # Don't touch entries from failed platforms
    if url in fresh_urls.get(platform, set()):
        continue  # Still active in fresh data — keep

    # URL was not returned by the platform's fresh fetch.
    # Keep it only during the "recent" grace period.
    status = classify(c["startTime"], c["duration"], now)
    if status != "recent":
        urls_to_evict.append(url)

for url in urls_to_evict:
    del stored[url]

if urls_to_evict:
    print(f"🗑️  Evicted {len(urls_to_evict)} stale/cancelled contest(s).")

# ── Step 4 & 5: Recalculate status, drop contests older than 3 days ───────────

final: list[dict] = []
dropped = 0

for c in stored.values():
    status = classify(c["startTime"], c["duration"], now)
    if status is None:
        dropped += 1
        continue  # Ended > 3 days ago — remove
    final.append({**c, "status": status})

if dropped:
    print(f"🗑️  Dropped {dropped} contest(s) that ended more than 3 days ago.")

# ── Step 6: Deduplication guard (URL-keyed store already prevents duplicates,
#            but assert here for safety) ─────────────────────────────────────

seen_urls: set[str] = set()
deduped: list[dict] = []
for c in final:
    if c["url"] not in seen_urls:
        seen_urls.add(c["url"])
        deduped.append(c)

if len(deduped) < len(final):
    print(f"⚠️  Removed {len(final) - len(deduped)} duplicate(s).")
final = deduped

# ── Step 7: Sort ──────────────────────────────────────────────────────────────

final.sort(key=sort_key)

# ── Step 8: Save ──────────────────────────────────────────────────────────────

with open(ALLCONTEST_PATH, "w", encoding="utf-8") as fh:
    json.dump(final, fh, indent=2, ensure_ascii=False)

# ── Summary ───────────────────────────────────────────────────────────────────

counts: dict[str, int] = {"running": 0, "future": 0, "recent": 0}
for c in final:
    counts[c["status"]] += 1

print(f"\n✅  AllContest.json updated — {len(final)} contest(s) kept.")
print(f"    🟢 Running : {counts['running']}")
print(f"    🔵 Future  : {counts['future']}  (within next 14 days)")
print(f"    🕐 Recent  : {counts['recent']}  (ended within last 3 days)")

if errored_platforms:
    print(f"\n⚠️  Fetch errors (existing entries preserved): "
          f"{', '.join(sorted(errored_platforms))}")