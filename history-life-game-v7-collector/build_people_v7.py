#!/usr/bin/env python3
"""Wikipedia/Wikidata biography collector. Real records only; never fabricates records.

Usage: WIKIMEDIA_CONTACT='https://github.com/YOUR_ACCOUNT/YOUR_REPO' python build_people_v7.py --limit 3000
"""
import argparse, datetime, json, os, pathlib, re, sys, time, urllib.error, urllib.parse, urllib.request
from collections import Counter

API='https://ja.wikipedia.org/w/api.php'
SPARQL='https://query.wikidata.org/sparql'
CONTACT=os.environ.get('WIKIMEDIA_CONTACT','').strip()
if not CONTACT:
 print('ERROR: set WIKIMEDIA_CONTACT to a working project URL or email for Wikimedia User-Agent.',file=sys.stderr);sys.exit(2)
UA=f'JinseiNoTsuzukiCollector/0.7 ({CONTACT}) Python-urllib'
THEMES={
'explore':['転職','退学','中退','移住','転居','放浪','渡航','辞職','移転'],
'make':['創作','執筆','小説','作曲','絵画','映画','漫画','制作','展覧会'],
'persistence':['研究','修行','練習','実験','博士','大学院','長年'],
'risk':['起業','創業','設立','独立','経営','革命','挑戦'],
'independent':['独学','独自','単独','自立','離脱'],
'uncertain':['失敗','貧困','失業','解雇','挫折','困窮','苦難','破産'],
'study':['大学','学校','研究','学問','科学','教育','入学','卒業'],
'social':['協力','共同','結婚','支援','交流','団体','仲間']}
NEGATION=re.compile(r'(?:しなかった|されなかった|していない|ではない|せず|失敗していない|未経験|噂|と誤認)')
OTHER_CONTEXT=re.compile(r'(?:父|母|兄|弟|姉|妹|子供|息子|娘|妻|夫|友人|師匠|祖父|祖母)(?:が|は|の)')

def request(base, params):
 url=base+'?'+urllib.parse.urlencode(params)
 headers={'User-Agent':UA,'Accept':'application/json'}
 for attempt in range(6):
  try:
   with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=55) as r:
    return json.load(r)
  except urllib.error.HTTPError as e:
   if e.code not in (429,500,502,503,504):raise
   delay=min(90,int(e.headers.get('Retry-After','0') or 0) or 2**(attempt+1))
   print(f'HTTP {e.code}: pause {delay}s',file=sys.stderr,flush=True)
   time.sleep(delay)
  except (TimeoutError, urllib.error.URLError) as e:
   print(f'Network retry {attempt+1}: {e}',file=sys.stderr,flush=True)
   time.sleep(min(60,2**(attempt+1)))
 raise RuntimeError('Requests repeatedly failed; checkpoint saved')

def discover(limit,offset):
 # No query-time sorting for speed. Dedup by QID locally; OFFSET can be expensive.
 q=f'''SELECT ?person ?birth ?article WHERE {{
 ?person wdt:P31 wd:Q5; wdt:P569 ?birth.
 ?article schema:about ?person; schema:isPartOf <https://ja.wikipedia.org/>.
 FILTER(YEAR(?birth)>=1500 && YEAR(?birth)<=2005)
 }} LIMIT {limit} OFFSET {offset}'''
 data=request(SPARQL,{'query':q,'format':'json'})
 out=[]
 for b in data.get('results',{}).get('bindings',[]):
  u=b['article']['value'];birth=b['birth']['value'][:10]
  if '/wiki/' not in u or not re.fullmatch(r'\d{4}-\d\d-\d\d',birth):continue
  out.append({'id':b['person']['value'].rsplit('/',1)[-1], 'name':urllib.parse.unquote(u.split('/wiki/')[-1]).replace('_',' '),'birth':birth,'url':u})
 return out

def extracts(batch):
 d=request(API,{'action':'query','prop':'extracts','explaintext':'1','redirects':'1','format':'json','formatversion':'2','titles':'|'.join(x['name'] for x in batch)})
 pages=d.get('query',{}).get('pages',[])
 texts={p.get('title','').replace(' ','_'):p.get('extract','') for p in pages if not p.get('missing')}
 redirects={r['from'].replace(' ','_'):r['to'].replace(' ','_') for r in d.get('query',{}).get('redirects',[])}
 normalized={r['from'].replace(' ','_'):r['to'].replace(' ','_') for r in d.get('query',{}).get('normalized',[])}
 result={}
 for p in batch:
  name=p['name'].replace(' ','_'); name=normalized.get(name,name);name=redirects.get(name,name)
  result[p['id']]=texts.get(name,'')
 return result

def events(text,birth_year,title):
 seen=set();out=[]
 for sentence in re.split(r'(?<=[。！？])|\n+',text):
  sentence=re.sub(r'\s+',' ',sentence).strip()
  if not 14<=len(sentence)<=320 or NEGATION.search(sentence):continue
  yrs=set(map(int,re.findall(r'(?<!\d)(1[5-9]\d{2}|20\d{2})年',sentence)))
  if len(yrs)!=1:continue
  year=next(iter(yrs));age=year-birth_year
  if age<0 or age>110 or year>datetime.date.today().year:continue
  tags=[k for k,terms in THEMES.items() if any(term in sentence for term in terms)]
  if not tags:continue
  if (age,sentence) in seen:continue
  seen.add((age,sentence))
  out.append({'age':age,'calendar_year':year,'text':sentence[:230], 'tags':tags,
     'confidence':.72 if OTHER_CONTEXT.search(sentence) else .89,'source_title':title})
 return sorted(out,key=lambda e:e['age'])[:85]

def atomic_json(path, value):
 tmp=path.with_suffix(path.suffix+'.tmp')
 tmp.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':')),encoding='utf-8');tmp.replace(path)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--limit',type=int,default=3000)
 ap.add_argument('--output',default='people.json');ap.add_argument('--offset',type=int,default=0)
 ap.add_argument('--max-scanned',type=int,default=60000);ap.add_argument('--min-events',type=int,default=2)
 ap.add_argument('--delay',type=float,default=1.1);args=ap.parse_args()
 if args.limit<1 or args.max_scanned<args.limit:ap.error('invalid limit/max-scanned')
 output=pathlib.Path(args.output);partial=output.with_suffix('.partial.json')
 data={}
 if partial.exists():
  for p in json.loads(partial.read_text(encoding='utf8')):data[p['id']]=p
 off=args.offset;scanned=0;failures=0
 try:
  while len(data)<args.limit and scanned<args.max_scanned:
   batch=discover(min(100,args.max_scanned-scanned),off)
   off+=min(100,args.max_scanned-scanned);scanned+=100
   if not batch:break
   for i in range(0,len(batch),15):
    chunk=[p for p in batch[i:i+15] if p['id'] not in data]
    if not chunk:continue
    pages=extracts(chunk)
    for p in chunk:
     p['events']=events(pages.get(p['id'],''),int(p['birth'][:4]),p['name'])
     if len(p['events'])>=args.min_events:data[p['id']]=p
    atomic_json(partial,list(data.values()))
    print(f'Collected {len(data)}/{args.limit}; scanned {scanned}',flush=True)
    if len(data)>=args.limit:break
    time.sleep(args.delay)
   failures=0;time.sleep(args.delay)
 except KeyboardInterrupt:
  print('Interrupted: exporting collected records',file=sys.stderr)
 except Exception as exc:
  print(f'Stopped because of API error: {exc}',file=sys.stderr)
 values=list(data.values())[:args.limit]
 payload={'version':2,'source':'ja.wikipedia.org / query.wikidata.org','extraction':'dated keyword heuristic; NOT AI reasoning',
  'collected_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'records':values}
 atomic_json(output,payload)
 counts=Counter(t for p in values for e in p['events'] for t in e['tags'])
 report={'requested_people':args.limit,'actual_people':len(values),'total_dated_events':sum(len(p['events']) for p in values),
         'scanned_rows_approx':scanned,'unique_ids':len(set(p['id'] for p in values)),
         'people_with_5_events':sum(len(p['events'])>=5 for p in values),'by_theme':dict(counts),
         'completed':len(values)>=args.limit,'age_precision':'year-only, may be off by 1 year',
         'limitations':'Events are extracted heuristically and may describe others; manual review needed.'}
 atomic_json(output.with_name('data-quality-report.json'),report)
 print(json.dumps(report,ensure_ascii=False,indent=2))
 if not report['completed']:sys.exit(3)
if __name__=='__main__':main()
