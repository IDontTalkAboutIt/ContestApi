# Minimal contest-data versioning

This patch keeps `AllContest.json` unchanged.

## What changed

- Added `DataVersion.json`
- `update_all.py` compares meaningful contest data before/after an update.
- If the contest data changed, `DataVersion.json` increments by 1.
- A change to the derived `status` field alone does not increment the version.
- `.github/workflows/Update.yml` now commits `DataVersion.json` together with `AllContest.json`.

## Example

```json
{
  "version": 2
}
```

Your Android app does not need to parse this file yet. Later, the Cloudflare/FCM layer can watch this version and notify the app when it changes.
