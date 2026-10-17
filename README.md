# Wild Friends public statistics relay

Fetches the public Tencent Wild Rift statistics JSON and publishes its original bytes, without champion filtering or tier recalculation. No member data, credentials, or Wild Friends server keys are stored here.

Source: https://mlol.qt.qq.com/go/lgame_battle_info/hero_rank_list_v2

GitHub Actions checks the source every 30 minutes. Failed validation keeps the last successful file. Scheduled jobs may run later than their scheduled time. Wild Friends independently validates champion IDs, dates and values before adopting data.

`data/relay.json` records the last source check, checksum and exact original JSON text. A failed fetch publishes an explicit failure status while preserving the last valid raw data file. The app rejects stale relay checks and failure statuses.

추천 빌드와 일반 협곡 조합은 loadouts.py가 2시간마다 확인한다. 작은 상태 파일의 해시가 바뀔 때만 서버가 원문 묶음을 다운로드한다. 원문, URL, 해시는 공개 게임 자료에 한해 저장하며 불완전한 수집은 마지막 정상 묶음을 덮지 않는다.


## Scheduling and recovery

GitHub checks at minute13 and43. Because GitHub scheduled events can be delayed or dropped, Lightsail independently checks the three small relay status files every5minutes. Numeric collection older than35minutes, loadouts older than155minutes, or game data older than395minutes wakes this workflow using a push to the dedicated `refresh-trigger` branch. Failed/invalid status also requests recovery. An active run younger than20minutes and a persisted30minute dispatch cooldown prevent duplicate runs. The source collection itself remains in GitHub; Lightsail never performs the large Tencent collection.

The trigger branch contains the unchanged `main` tree, uses an explicit force-with-lease, and never changes `main` or public data. All three jobs explicitly check out `main`. A repository-scoped SSH deploy key is stored only in the Lightsail private directory; no personal GitHub token is copied to the server. The systemd service/timer and Python watchdog sources are maintained in the application repository. See `server/deploy/wf-statistics-watchdog.*` and `ops/tencent-statistics-relay/watchdog.py` there. Restart-persistent state is kept in `/var/lib/wf-statistics-watchdog/state.json`.
