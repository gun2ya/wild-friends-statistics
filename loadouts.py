"""Collect public Tencent recommendations; a failed run never replaces the last bundle."""
import argparse
import concurrent.futures
import datetime
import hashlib
import json
from pathlib import Path
import time
import urllib.request

BASE = 'https://mlol.qt.qq.com/go/lgame_battle_info/'
CATALOG = 'https://game.gtimg.cn/images/lgamem/act/lrlib/js/'
KINDS = ('hero_tech', 'hero_equip_core', 'hero_equip_shoe', 'hero_equip_rune', 'hero_equip_skill')
INTERVAL = 7200
MAX_FILE = 2 * 1024 * 1024


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')))
    tmp.replace(path)


def request(url):
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'WildFriends-Loadouts/1.0', 'Accept': 'application/json', 'Referer': 'https://lolm.qq.com/'})
            with urllib.request.urlopen(req, timeout=10) as response:
                raw = response.read(MAX_FILE + 1)
            if len(raw) > MAX_FILE:
                raise ValueError('Response too large')
            obj = json.loads(raw)
            empty = obj.get('result') == 1000 and obj.get('data') is None and obj.get('msg') == 'no data' and 'hero_equip_' in url
            if '/go/' in url and not empty and (type(obj.get('result')) is not int or obj['result'] != 0):
                raise ValueError('Unsuccessful source result')
            return {'url': url, 'raw': raw.decode('utf8'), 'sha256': hashlib.sha256(raw).hexdigest()}
        except Exception:
            if attempt: raise
            time.sleep(1)


def collect(destination, force=False):
    status_file, bundle_file, work_file = [destination / n for n in ('loadouts-status.json', 'loadouts-data.json', 'loadouts-work.json')]
    now = time.time()
    if not force and status_file.exists():
        last = json.loads(status_file.read_text())
        if last.get('ok') and now - datetime.datetime.fromisoformat(last['checkedAt']).timestamp() < INTERVAL:
            print('Recommendations not due');return
    started = time.monotonic()
    checked = datetime.datetime.now(datetime.timezone.utc).isoformat()
    records = {}; failures = []
    try:
        heroes = request(CATALOG + 'heroList/hero_list.js')
        ids = sorted(json.loads(heroes['raw'])['heroList'])
        if not 100 <= len(ids) <= 300 or any(not x.isdecimal() for x in ids):
            raise ValueError('Invalid champion catalog')
        records['heroes'] = heroes
        jobs = [('items', CATALOG+'equip/equip.js'), ('runes', CATALOG+'rune/rune.js'), ('spells', CATALOG+'skill/skill.js')]
        for hid in ids:
            for kind in KINDS:
                query = '?hero_id='+hid+('&mode=classic_model&source_game_zone=lgame&game_zone=lgame' if kind == 'hero_tech' else '')
                jobs.append((hid+'/'+kind, BASE+kind+query))
        cached = json.loads(work_file.read_text()) if work_file.exists() else {}
        cache_start = cached.get('startedAt', now)
        cached = cached.get('records', {}) if now-cache_start < INTERVAL else {}
        if not cached:cache_start=now
        def run(job):
            key, url = job
            if time.monotonic()-started > 600: return key, None, 'collection deadline'
            try:
                old = cached.get(key)
                if old and old['url']==url and hashlib.sha256(old['raw'].encode()).hexdigest()==old['sha256']:
                    return key, old, None
                return key, request(url), None
            except Exception as error:
                return key, None, type(error).__name__
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            for index, (key, value, error) in enumerate(pool.map(run, jobs)):
                if error:failures.append({'key':key,'error':error})
                else:records[key]=value
                if index % 25 == 0:
                    write(work_file, {'startedAt':cache_start,'records':records})
                    print('Collected', index+1, '/', len(jobs), 'failures',len(failures),flush=True)
        if failures:
            write(work_file, {'startedAt':cache_start,'records':records})
            raise ValueError('Incomplete recommendations collection')
        # Retrieval clocks are intentionally excluded from the large content hash.
        bundle = {'formatVersion':1,'champions':ids,'records':records}
        encoded=json.dumps(bundle,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
        digest=hashlib.sha256(encoded).hexdigest()
        if not bundle_file.exists() or hashlib.sha256(bundle_file.read_bytes()).hexdigest()!=digest:
            tmp=bundle_file.with_suffix('.tmp');tmp.write_bytes(encoded);tmp.replace(bundle_file)
        write(status_file,{'formatVersion':1,'ok':True,'checkedAt':checked,'sha256':digest,'champions':len(ids),'records':len(records),'intervalSeconds':INTERVAL})
        work_file.unlink(missing_ok=True)
        print('Recommendations complete',len(ids),len(records),digest,flush=True)
    except Exception:
        write(status_file,{'formatVersion':1,'ok':False,'checkedAt':checked,'failed':failures[:30],'intervalSeconds':INTERVAL})
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=Path('data'));parser.add_argument('--force',action='store_true')
    args=parser.parse_args();collect(args.output,args.force)
