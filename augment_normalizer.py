"""Source-ID preserving normalization for Wild Rift AAA ARAM. No Rift data joins."""
import copy,datetime,hashlib,json,math,re
QUALITIES={'255':'all','2':'prismatic','3':'gold','4':'silver','0':'special'}
def revision(value):
    return hashlib.sha256(json.dumps({k:v for k,v in value.items()if k not in ('revision','checkedAt')},sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def normalize_catalog(raw,localization,overrides):
    entries=raw['gainhexList'];entries=list(entries.values())if isinstance(entries,dict)else entries;items={}
    for row in entries:
        sid=str(row['gainHexId'])
        if sid in items or not re.fullmatch(r'\d+',sid):raise ValueError('Duplicate/invalid source identity')
        loc=localization.get(sid,{}) if isinstance(localization,dict)else {};verified=loc.get('status')=='reviewed'
        def array(k):
            v=row.get(k,'[]');return list(dict.fromkeys(str(x)for x in (json.loads(v)if isinstance(v,str)else v)if x))
        items[sid]={'sourceId':sid,'name':loc.get('name')if verified and loc.get('name')else row['name'],'nameKo':loc.get('name')if verified else None,'nameSource':row['name'],'nameStatus':'reviewed'if verified else 'source','quality':QUALITIES.get(str(row.get('quality','0')),'special'),'icon':row.get('iconPath',''),'basicDescription':loc.get('basicDescription',row.get('detaildesc',''))if verified else row.get('detaildesc',''),'enhancedDescription':loc.get('enhancedDescription',row.get('specialdesc',''))if verified else row.get('specialdesc',''),'tags':array('tagitems')+array('careertag'),'series':row.get('hextag',''),'sourceVersion':raw.get('version'),'sourceFileTime':raw.get('fileTime')}
        override=overrides.get(sid)
        if override:
            if not override.get('evidence'):raise ValueError('Patch override needs evidence')
            items[sid].update({k:v for k,v in override.items()if k in ('basicDescription','enhancedDescription','nameKo','name','quality')});items[sid]['patchEvidence']=override['evidence']
    result={'schemaVersion':1,'source':'Tencent CN','sourceUrl':'https://game.gtimg.cn/images/lgamem/act/lrlib/js/gainhex/gainhex.js','sourceVersion':raw.get('version'),'sourceFileTime':raw.get('fileTime'),'checkedAt':stamp(),'items':items,'coverage':{'records':len(items),'activeStatus':'unverified'}};result['revision']=revision(result);return result

def normalize_champion_stats(raw,champion,quality,catalog):
    if raw.get('result')!=0 or quality not in ('all','silver','gold','prismatic'):raise ValueError('Invalid source result/quality')
    payload=raw.get('data',{}).get('result')
    if not isinstance(payload,str):raise ValueError('Missing source payload')
    data=json.loads(payload);day=data['dtstatdate'];date=datetime.datetime.strptime(day,'%Y%m%d').date().isoformat();rows=[];seen=set()
    for packed in data.get('augment_data','').split('#'):
        if not packed:continue
        rank,sid,filter_quality,appear,win,grade=packed.split('_')
        if sid in seen or sid not in catalog['items'] or not rank.isdigit()or int(rank)<1:raise ValueError('Duplicate/unknown augment or rank')
        seen.add(sid);a,w=float(appear),float(win)
        if any(not math.isfinite(v)or not 0<=v<=1 for v in (a,w)):raise ValueError('Invalid source rate')
        actual=catalog['items'][sid]['quality']
        if quality!='all'and actual!=quality:raise ValueError('Source quality disagrees with catalog')
        rows.append({'sourceId':sid,'sourceRank':int(rank),'quality':actual,'recommendLevel':grade,'winPercent':w*100,'appearPercent':a*100})
    if not rows:raise ValueError('Source group empty')
    return {'champion':champion,'quality':quality,'sourceDate':date,'checkedAt':stamp(),'rows':rows}

def merge_snapshot(previous,incoming):
    out=copy.deepcopy(previous);out.update({k:copy.deepcopy(v)for k,v in incoming.items()if k not in ('champions','championSummaries')})
    for cid,group in incoming.get('champions',{}).items():out.setdefault('champions',{}).setdefault(cid,{}).setdefault('qualities',{}).update(copy.deepcopy(group.get('qualities',{})))
    out.setdefault('championSummaries',{}).update(copy.deepcopy(incoming.get('championSummaries',{})))
    out['revision']=revision(out);return out
