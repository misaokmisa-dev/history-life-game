import sys,json,datetime
path=sys.argv[1]; goal=int(sys.argv[2]); data=json.load(open(path,encoding='utf8'))
people=data['records']; ids=[p['id'] for p in people]
assert len(people)>=goal,(len(people),goal)
assert len(set(ids))==len(ids),'duplicate IDs'
count=0
for p in people:
 assert p['id'].startswith('Q') and p['name'] and p['url'].startswith('https://') and p['events']
 birth=int(p['birth'][:4])
 for e in p['events']:
  assert e['calendar_year']-birth==e['age'] and 0<=e['age']<=110
  assert e['source_title'] and e['tags'] and e['text'];count+=1
print('Validated',len(people),'unique real-source biographies and',count,'age-tagged text excerpts')
