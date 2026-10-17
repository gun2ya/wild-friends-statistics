# Wild Friends public statistics relay

Fetches the public Tencent Wild Rift statistics JSON and publishes its original bytes, without champion filtering or tier recalculation. No member data, credentials, or Wild Friends server keys are stored here.

Source: https://mlol.qt.qq.com/go/lgame_battle_info/hero_rank_list_v2

GitHub Actions checks the source every 30 minutes. Failed validation keeps the last successful file. Scheduled jobs may run later than their scheduled time. Wild Friends independently validates champion IDs, dates and values before adopting data.

`data/relay.json` records the last source check, checksum and exact original JSON text. A failed fetch publishes an explicit failure status while preserving the last valid raw data file. The app rejects stale relay checks and failure statuses.

## Recommendation feeds

`loadouts.py` checks public normal-mode item/rune/spell combinations and recommended builds every two hours. It uses four workers with a ten-minute collection deadline. The public champion catalog drives coverage. Original response bodies, request URLs and SHA-256 hashes are preserved in `data/loadouts-data.json`; the small `data/loadouts-status.json` reports completion or failure. An incomplete collection preserves the last complete payload and records resumable public responses in `loadouts-work.json`. These feeds contain only public Tencent game data, never Wild Friends member data.

The backend checks the small status document and downloads the full payload only when its hash changes. Missing source data and outdated records are handled separately by the application's validator.
