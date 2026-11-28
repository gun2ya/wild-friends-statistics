"""CI public-data relay. No user accounts, cookies or authentication tokens are read."""
from pathlib import Path
import concurrent.futures,datetime,hashlib,json,sys,time,urllib.request
from augment_normalizer import normalize_catalog,normalize_champion_stats,merge_snapshot,stamp
D=Path('data');D.mkdir(exist_ok=True);STATUS=D/'augments-status.json';OUT=D/'augments-data.json'
if '--force'not in sys.argv and STATUS.exists():
 try:
  status=json.loads(STATUS.read_text());checked=datetime.datetime.fromisoformat(status['checkedAt']).timestamp()
  if status.get('ok')and time.time()-checked<1800:print('Already checked recently');sys.exit(0)
 except (ValueError,KeyError):pass
heroes=json.loads(Path('augments-champions.json').read_text());previous=json.loads(OUT.read_text())if OUT.exists()else{}
def read(url):
 for i in range(3):
  try:
   raw=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://lolm.qq.com/'}),timeout=18).read();return json.loads(raw)
  except Exception:
   if i==2:raise
   time.sleep(1)
try:
 raw=read('https://game.gtimg.cn/images/lgamem/act/lrlib/js/gainhex/gainhex.js');catalog=normalize_catalog(raw,{},{});state={'schemaVersion':1,'source':'Tencent CN','checkedAt':stamp(),'period':1,'champions':{},'championSummaries':{},'failures':[]}
 def collect(job):
  hid,cid,q,code=job
  try:
   url=f'https://mlol.qt.qq.com/go/lgame_battle_info/hero_tech?hero_id={hid}'if q=='summary'else f'https://mlol.qt.qq.com/go/battle_info/odp_proxy/lgame_hex_card_rank?heroid={hid}&period=1&hexquality={code}'
   original=read(url)
   if q=='summary':
    v=original['data']['hex_model']['item_data'];parse=lambda k:float(v[k].rstrip('%'))if v.get(k)else None
    value={'champion':cid,'winPercent':parse('win_rate'),'appearPercent':parse('appear_rate'),'tier':None,'banPercent':None,'sourceDate':None,'checkedAt':stamp()}
    if value['winPercent']is None:raise ValueError('Missing champion summary')
   else:value=normalize_champion_stats(original,cid,q,catalog)
   value['sourceUrl']=url;value['sourceSha256']=hashlib.sha256(json.dumps(original,sort_keys=True,separators=(',',':')).encode()).hexdigest();return cid,q,value,None
  except Exception as error:return cid,q,None,str(error)
 jobs=[(hid,cid,q,code)for hid,cid in heroes.items()for q,code in [('all','255'),('silver','4'),('gold','3'),('prismatic','2'),('summary',None)]]
 with concurrent.futures.ThreadPoolExecutor(max_workers=4)as pool:
  for i,(cid,q,value,error)in enumerate(pool.map(collect,jobs),1):
   if error:state['failures'].append({'champion':cid,'quality':q,'error':error})
   elif q=='summary':state['championSummaries'][cid]=value
   else:state['champions'].setdefault(cid,{'qualities':{}})['qualities'][q]=value
   if i%100==0:print('collected',i,'/',len(jobs),flush=True)
 state['coverage']={'expectedChampions':len(heroes),'champions':len(state['champions']),'groups':sum(len(g['qualities'])for g in state['champions'].values()),'summaries':len(state['championSummaries'])}
 if state['coverage']['groups']<len(heroes)*3:raise ValueError('Widespread augment source failure')
 payload={'catalog':catalog,'rawCatalog':raw,'statistics':merge_snapshot(previous.get('statistics',{}),state)};blob=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode();OUT.write_bytes(blob)
 status={'formatVersion':1,'ok':True,'checkedAt':stamp(),'sha256':hashlib.sha256(blob).hexdigest(),'coverage':state['coverage'],'partialFailures':state['failures']};STATUS.write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n');print(json.dumps(state['coverage']))
except Exception as error:
 STATUS.write_text(json.dumps({'formatVersion':1,'ok':False,'checkedAt':stamp(),'error':str(error)},indent=2)+'\n');raise
