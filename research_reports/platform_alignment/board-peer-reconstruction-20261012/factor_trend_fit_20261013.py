import sys,json,yaml,requests,itertools,numpy as np,pandas as pd
sys.path.insert(0,'research_reports/platform_alignment/bc-peer-pools-20261012');import method_search_v3b as m
ROOT='research_reports/platform_alignment/board-peer-reconstruction-20261012';cfg=yaml.safe_load(open('/home/minkefu/.pandaai/config.yaml'));base=cfg['gateway_url'].rstrip('/');h={'Authorization':cfg['token'],'uid':str(cfg['uid'])}
fids={'illiq':'4fc0a28b8deeb96631b3716c','lowturn':'dcb1cfe1e91da35bda852fa2','lowvol':'0810f13be557e7cf8136f4e5','rsi':'62177122331952ce77d09edb','size':'ab026e5ba65889944ec6fb30'}
pub={}
for k,fid in fids.items():
 d=requests.get(base+f'/arenaRanking/pools/0a4f3ddbc4bb8b74720587a3/factors/{fid}/out-of-sample-analysis',params={'tradeDate':'20261009'},headers=h,timeout=30).json()['data'];pub[k]=d;print(k,[(x['exposure_date'],x['rank_ic'],x['sample_count']) for x in d['trend']['points']])
json.dump(pub,open(ROOT+'/factor_trends_public_20261013.json','w'),ensure_ascii=False,indent=2)
cal,stocks,fields,pos,dates,atoms=m.load();complete=pos+4<len(cal);y=np.full((len(pos),len(stocks)),np.nan);y[complete]=fields['close'][pos[complete]+4]/fields['close'][pos[complete]+1]-1
D={pd.Timestamp(d).strftime('%Y%m%d'):i for i,d in enumerate(dates)}
def corr(a,b):
 ok=np.isfinite(a)&np.isfinite(b);aa=a[ok];bb=b[ok];return float(np.corrcoef(aa,bb)[0,1]) if ok.sum()>20 else np.nan
# local candidate groups
sets={'illiq':[k for k in atoms if k.startswith(('illiquidity','illiq_','amihud','lowamount','lowmaxret','turnimpact'))], 'lowturn':[k for k in atoms if k.startswith('lowturn')], 'lowvol':[k for k in atoms if k.startswith(('lowvol','lowrange','downside','rangevol'))], 'rsi':[k for k in atoms if k.startswith(('rsi','reversal','a078rev'))], 'size':[k for k in atoms if k in ('smallsize','lowamount5','lowamount10','lowamount20','lowamount60','lowamount120','lowprice')]}
rows=[]
for g,ks in sets.items():
 target=np.array([x['rank_ic'] for x in pub[g]['trend']['points']]); dates_pub=[x['exposure_date'] for x in pub[g]['trend']['points']]
 for k in ks:
  vals=[]
  for d in dates_pub:
   i=D.get(d); vals.append(corr(atoms[k][i],y[i]) if i is not None else np.nan)
  vals=np.array(vals);err=float(np.nanmean((vals-target)**2));rho=float(np.corrcoef(vals,target)[0,1]) if np.isfinite(vals).sum()>2 else np.nan;rows.append({'group':g,'candidate':k,'mse':err,'corr_to_public':rho,'local':vals.tolist(),'public':target.tolist()})
for g in sets:
 print('\n',g)
 for x in sorted([r for r in rows if r['group']==g],key=lambda z:z['mse'])[:20]:print(x)
json.dump(rows,open(ROOT+'/factor_trend_fit_20261013.json','w'),ensure_ascii=False,indent=2)
