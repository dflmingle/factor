"""Offline frozen-port equivalence and same-date local Top20 baseline."""
import sys,json,pickle,hashlib,warnings
from pathlib import Path
import numpy as np,pandas as pd
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
SEARCH=ROOT/'research_reports/peer_reconstruction/top50-20261013/search_v1'
sys.path.insert(0,str(SEARCH))
from grammar import Expr
from engine import Interpreter,standardize
warnings.filterwarnings('ignore',category=RuntimeWarning)
warnings.filterwarnings('ignore',category=FutureWarning)
scope={'Factor':type('Factor',(),{})}
exec((HERE/'star_coin_frozen_pool.py').read_text(),scope)
factors=pd.read_pickle(HERE/'repaint_fields_200.pkl')
map_fields={'market_cap':'cap','book_to_market_ratio_lf':'bm','ratio_ep_ttm':'ep','ratio_cfp_ttm':'cfp','ratio_sp_ttm':'sp'}
fields={map_fields.get(k,k):v.unstack(1).to_numpy(dtype='f4') for k,v in factors.items()}
template=factors['close'].unstack(1).astype(float)
mask=np.isfinite(fields['cap'])&(fields['cap']>0)
eligible=mask & np.isfinite(fields['turnover']) & ~(fields['volume']<=0) & ~(fields['amount']<=0)
eligible &= ~np.isclose(fields['high'],fields['low'],rtol=1e-8,atol=1e-8)
engine=Interpreter(fields)
legs=[];checks=[]
for j,(tree,direction) in enumerate(zip(scope['TREES'],scope['DIRECTIONS'])):
    expected=engine.evaluate(Expr.from_json(tree));actual=scope['_evaluate'](tree,fields,template,mask)
    assert np.array_equal(np.isnan(expected),np.isnan(actual)),j
    delta=float(np.nanmax(abs(expected-actual)));assert delta==0,(j,delta)
    legs.append(np.float32(direction)*standardize(expected.astype(float),eligible))
    checks.append({'leg':j,'max_abs_difference':delta})
expected=np.zeros(template.shape,dtype='f4')
for leg in legs: expected+=leg
expected/=np.float32(len(legs))
actual=scope['StarCoinFrozenPoolFactor']().calculate(factors).unstack(1).to_numpy()
assert np.array_equal(np.isnan(expected),np.isnan(actual))
assert float(np.nanmax(abs(expected-actual)))==0
result={'operator_equivalence':'PASS','composite_equivalence':'PASS','stocks':len(template.columns),'dates':len(template),'legs':checks,'nan_mask_equal':True,'max_abs_difference':0}
(HERE/'port_equivalence.json').write_text(json.dumps(result,indent=2)+'\n')
# Full universe frozen cached panels: no Market constructor or shared-cache writes.
cal,stocks,fields=pickle.load((ROOT/'research_reports/platform_alignment/bc-peer-pools-20261012/market_extended.pkl').open('rb'))
cal=pd.DatetimeIndex(cal);stocks=pd.Index(stocks)
recent=cal[cal>=pd.Timestamp('20260801')];signal=pd.Timestamp('20261008');i=recent.get_loc(signal);p=cal.get_loc(signal)
mask=np.isfinite(fields['cap'][p])&(fields['cap'][p]>0)&np.isfinite(fields['turnover'][p])
mask &=~((fields['volume'][p]<=0)|(fields['amount'][p]<=0)|np.isclose(fields['high'][p],fields['low'][p],rtol=1e-8,atol=1e-8))
nomask=mask.copy()
names=pd.read_parquet(ROOT/'quantlab/.quantlab/cache/research/cn_equity/stock_basic/namechange.parquet')
for symbol,g in names.groupby('ts_code',sort=False):
    j=stocks.get_indexer([symbol])[0]
    if j<0:continue
    flag=False
    for r in g.dropna(subset=['start_date']).sort_values('start_date').itertuples():
        ann=max(r.start_date,r.ann_date) if pd.notna(r.ann_date) else r.start_date
        if signal>=ann:flag='ST' in str(r.name).upper()
    if flag:mask[j]=False
panels=[]
cache=ROOT/'research_reports/peer_reconstruction/star-coin-alpha-transfer-20261016-v2/diff_panels'
for tree in scope['TREES']:
    expr=Expr.from_json(tree);key=hashlib.sha256(expr.key().encode()).hexdigest()
    a=np.load(cache/(key+'.npy'),mmap_mode='r');assert len(a)==len(recent)
    panels.append(np.array(a[i],dtype=float))
public=json.loads((ROOT/'research_reports/peer_reconstruction/top50-20261013/public/holdings/18067f13fb2f894e0a45b181/20261009.json').read_text())
truth={r['symbol']:r for r in public['rows']}
out={'signal_date':'20261008','trade_date':'20261009','public_count':len(truth),'baselines':{}}
for label,m in [('competition_st_filtered',mask),('numeric_mask_only',nomask)]:
    legs=[standardize(a[None,:],m[None,:])[0]*np.float32(d) for a,d in zip(panels,scope['DIRECTIONS'])]
    composite=np.array(legs).sum(axis=0)/len(legs)
    valid=np.flatnonzero(m&np.isfinite(composite));order=valid[np.argsort(composite[valid],kind='stable')][::-1]
    rows=[{'rank':k+1,'symbol':str(stocks[j]),'value':float(composite[j]),'peer_rank':truth.get(str(stocks[j]),{}).get('rank')}for k,j in enumerate(order[:20])]
    held=set(stocks[order[:int(np.ceil(len(order)/10))]])
    out['baselines'][label]={'top20':rows,'top20_overlap':sum(r['peer_rank'] is not None and r['peer_rank']<=20 for r in rows),'top20_in_peer_holdings':sum(r['peer_rank'] is not None for r in rows),'full_holdings_overlap':len(held&set(truth))/len(truth),'full_count':len(held)}
assert abs(out['baselines']['competition_st_filtered']['full_holdings_overlap']-0.7808764940239044)<1e-12
(HERE/'local_same_date_baseline.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'equivalence':result,'baselines':{k:{a:b for a,b in v.items() if a!='top20'}for k,v in out['baselines'].items()}},ensure_ascii=False))
