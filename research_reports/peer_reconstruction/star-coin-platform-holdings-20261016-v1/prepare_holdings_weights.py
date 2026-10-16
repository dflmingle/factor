from pathlib import Path
import json,hashlib
OUT=Path(__file__).resolve().parent
base=(OUT/'star_coin_frozen_pool.py').read_text()
weights=[
 ('F-SCH1016-05','StarCoinHoldLatestA',[0.055,0.061,0.088,0.096,0.089,0.117,0.130,0.123,0.112,0.128],'latest Top20 priority; local five-snapshot hits 10,10,11,12,12; latest 12/20'),
 ('F-SCH1016-06','StarCoinHoldLatestB',[0.067,0.112,0.087,0.054,0.077,0.127,0.114,0.113,0.112,0.137],'latest Top20 priority, second independent weight solution; local hits 10,11,10,12,12'),
 ('F-SCH1016-07','StarCoinHoldRobust',[0.101,0.129,0.062,0.071,0.080,0.133,0.106,0.086,0.095,0.137],'history-balanced; local hits 11,9,12,14,11; highest five-date mean among retained robust solutions'),
]
lines=[]; rows=[]
for cand,cls,w,reason in weights:
 a=base.index('TREES = '); b=base.index('\nDIRECTIONS = ',a); c=base.index('\n\n\ndef _cast',b)
 src=base[:a]+'TREES = '+base[a+len('TREES = '):b]+'\nDIRECTIONS = [-1.0, -1.0, -1.0, -1.0, 1.0, -1.0, -1.0, -1.0, -1.0, 1.0]\nWEIGHTS = '+repr(w)+'\n'+base[c:]
 src=src.replace('class StarCoinFrozenPoolFactor',f'class {cls}Factor')
 src=src.replace('for tree, direction in zip(TREES, DIRECTIONS):','for tree, direction, weight in zip(TREES, DIRECTIONS, WEIGHTS):')
 src=src.replace('composite += np.float32(direction) * normalized','composite += np.float32(direction) * np.float32(weight) * normalized')
 path=OUT/(cand.lower()+'.py');path.write_text(src);lines.append(f'{cand} ~ {path.name} ~ 1');rows.append({'name':cand,'file':path.name,'weights':w,'reason':reason,'sha256':hashlib.sha256(src.encode()).hexdigest()})
(OUT/'candidates_holdings.txt').write_text('\n'.join(lines)+'\n');(OUT/'holdings_weight_candidates.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n');print(json.dumps(rows,ensure_ascii=False))
