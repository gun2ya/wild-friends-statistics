"""Publish only Tencent's public, unmodified statistics JSON after validation."""
import datetime
import hashlib
import json
from pathlib import Path
import time
import urllib.request

URL = 'https://mlol.qt.qq.com/go/lgame_battle_info/hero_rank_list_v2'
DESTINATION = Path('data/hero_rank_list_v2.json')
STATUS = Path('data/relay.json')


def status(ok, raw=None):
    value = {'formatVersion': 1, 'sourceUrl': URL, 'ok': ok,
             'checkedAt': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    if raw is not None:
        value.update(raw=raw.decode('utf-8'), sha256=hashlib.sha256(raw).hexdigest())
    STATUS.parent.mkdir(exist_ok=True)
    temp = STATUS.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')))
    temp.replace(STATUS)


def validate(raw):
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError('Response exceeds size limit')
    payload = json.loads(raw)
    if payload.get('result') != 0:
        raise ValueError('Unsuccessful source response')
    dates = set()
    for rank in ('1', '2', '3', '4'):
        lanes = payload['data'][rank]
        if set(lanes) != set('12345'):
            raise ValueError('Incomplete lane coverage')
        for lane, entries in lanes.items():
            if not entries:
                raise ValueError('Empty lane')
            for row in entries:
                if str(row['position']) != lane:
                    raise ValueError('Wrong lane')
                dates.add(datetime.datetime.strptime(row['dtstatdate'], '%Y%m%d').date())
                if not 0 <= int(row['strength_level']) <= 5 or int(row['strength']) < 1:
                    raise ValueError('Invalid source strength')
                for field in ('win_rate_percent', 'appear_rate_percent', 'forbid_rate_percent'):
                    if not 0 <= float(row[field]) <= 100:
                        raise ValueError('Invalid percentage')
    if len(dates) != 1 or max(dates) > datetime.datetime.now(datetime.timezone.utc).date() + datetime.timedelta(days=1):
        raise ValueError('Inconsistent source date')
    return dates.pop()


def main():
    for attempt in range(3):
        try:
            request = urllib.request.Request(URL, headers={'User-Agent': 'WildFriends-Statistics/1.0', 'Accept': 'application/json'})
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
            day = validate(raw)
            if DESTINATION.exists() and validate(DESTINATION.read_bytes()) > day:
                raise ValueError('Refusing to publish older data')
            DESTINATION.parent.mkdir(exist_ok=True)
            temp = DESTINATION.with_suffix('.tmp')
            temp.write_bytes(raw)
            temp.replace(DESTINATION)
            status(True, raw)
            print('Public statistics validated:', day)
            return
        except Exception:
            if attempt == 2:
                status(False)
                raise
            time.sleep(2)


if __name__ == '__main__':
    main()
