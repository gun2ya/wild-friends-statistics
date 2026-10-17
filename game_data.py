"""Read-only Tencent skill/item evidence; never edits the app's gameplay data."""
import argparse
import concurrent.futures
import datetime
import hashlib
import json
from pathlib import Path
import time
import urllib.request

BASE = 'https://game.gtimg.cn/images/lgamem/act/lrlib/js/'
INTERVAL = 21600
MAX_FILE = 2 * 1024 * 1024


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')))
    tmp.replace(path)


def request(url):
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'WildFriends-GameDataWatch/1.0', 'Accept': 'application/json', 'Referer': 'https://lolm.qq.com/'})
            with urllib.request.urlopen(req, timeout=10) as response:
                # Static CDN content can otherwise outlive a source edit.
                raw = response.read(MAX_FILE + 1)
            if len(raw) > MAX_FILE:
                raise ValueError('Response too large')
            json.loads(raw)
            return {'url': url, 'raw': raw.decode('utf8'), 'sha256': hashlib.sha256(raw).hexdigest()}
        except Exception:
            if attempt: raise
            time.sleep(1)


def collect(destination, force=False):
    status_file, bundle_file = [destination / n for n in ('game-data-status.json', 'game-data.json')]
    if not force and status_file.exists():
        last = json.loads(status_file.read_text())
        if last.get('ok') and time.time() - datetime.datetime.fromisoformat(last['checkedAt']).timestamp() < INTERVAL:
            print('Game data not due');return
    failures = [];records = {};started = time.monotonic()
    try:
        heroes = request(BASE + 'heroList/hero_list.js')
        roster = json.loads(heroes['raw'])['heroList'];ids = sorted(roster)
        if not 100 <= len(ids) <= 300 or any(not x.isdecimal() or str(roster[x].get('heroId')) != x for x in ids):
            raise ValueError('Invalid champion roster')
        records['heroes'] = heroes
        jobs = [('items', BASE + 'equip/equip.js')] + [(hid, BASE + 'hero/' + hid + '.js') for hid in ids]
        def run(job):
            key, url = job
            if time.monotonic() - started > 480:return key,None,'collection deadline'
            try:
                value=request(url);obj=json.loads(value['raw'])
                if key=='items':
                    if not isinstance(obj.get('equipList'),list) or not 100<=len(obj['equipList'])<=500:raise ValueError('Invalid item catalog')
                elif str(obj.get('hero',{}).get('heroId'))!=key or not isinstance(obj.get('spells'),list) or len(obj['spells'])<5:
                    raise ValueError('Invalid hero details')
                return key,value,None
            except Exception as error:return key,None,type(error).__name__
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            for index,(key,value,error) in enumerate(pool.map(run,jobs)):
                if error:failures.append({'key':key,'error':error})
                else:records[key]=value
                if index%25==0:print('Game data',index+1,'/',len(jobs),'failures',len(failures),flush=True)
        if failures:raise ValueError('Incomplete game data collection')
        bundle={'formatVersion':1,'champions':ids,'records':records}
        encoded=json.dumps(bundle,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode();digest=hashlib.sha256(encoded).hexdigest()
        if not bundle_file.exists() or hashlib.sha256(bundle_file.read_bytes()).hexdigest()!=digest:
            destination.mkdir(parents=True,exist_ok=True);tmp=bundle_file.with_suffix('.tmp');tmp.write_bytes(encoded);tmp.replace(bundle_file)
        write(status_file,{'formatVersion':1,'ok':True,'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sha256':digest,'champions':len(ids),'records':len(records),'intervalSeconds':INTERVAL})
        print('Game data complete',len(ids),len(records),digest,flush=True)
    except Exception:
        write(status_file,{'formatVersion':1,'ok':False,'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'failed':failures[:30],'intervalSeconds':INTERVAL})
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=Path('data'));parser.add_argument('--force',action='store_true')
    args=parser.parse_args();collect(args.output,args.force)
