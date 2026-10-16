#!/usr/bin/env python3
"""Replay directly mapped financial-only builders on the long PIT snapshot."""
import os
for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import importlib,json,argparse
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
import regime_long_history_data_20261014 as data
import regime_long_base_replay_20261014 as base
import regime_long_pit_fast_20261014 as pit

OUT=q.ROOT/'research_reports/platform_alignment/regime-long-financial-replay-v2-20261014'

def main():
    global OUT
    parser=argparse.ArgumentParser();parser.add_argument('--risk-composites',action='store_true');args_cli=parser.parse_args()
    if args_cli.risk_composites:OUT=q.ROOT/'research_reports/platform_alignment/regime-long-financial-risk-replay-20261014'
    OUT.mkdir(parents=True,exist_ok=True);cal,stocks,f=pd.read_pickle(data.training_market_path());q.dates_all=cal
    saved=pd.read_pickle(base.BASE/'signal_panels.pkl');formal=saved['dates'];first=cal.get_loc(formal[0]);hp=np.arange(first%10,first,10);hp=hp[hp>=252];pos=np.r_[hp,cal.get_indexer(formal)];grid=cal[pos];n=len(hp);cap=f['cap'][pos]
    q.OUT=OUT;q.CACHE=data.DATA/'combined_view'
    fin=pd.read_pickle(base.OUT/'financial_signal_snapshots.pkl')
    metadata=pd.read_csv(data.OUT/'all_factor_replay_inventory.csv');mainmeta=pd.read_csv(q.ROOT/'research_reports/platform_alignment/shu-mulvey-sjm-bl-20261014/factor_metadata.csv').set_index('key')
    signatures=['fin,cap,iv','fin,f,pos,iv','fin,f,pos,beta'] if args_cli.risk_composites else ['fin','fin,cap','fin,f,pos','f,fin,pos']
    eligible=metadata[metadata.adapter.isin(['values','build'])&metadata.arguments.isin(signatures)]
    import ast
    needed={ep:set() for ep in q.FIN_FIELDS}
    for script in eligible.builder_script.unique():
        tree=ast.parse((q.ROOT/script).read_text())
        module=importlib.import_module(script.split('/')[-1][:-3])
        for endpoint,cols in getattr(module,'FIELDS',{}).items():
            if endpoint in needed:needed[endpoint].update(cols)
        for node in ast.walk(tree):
            if isinstance(node,ast.Constant) and isinstance(node.value,str):
                parts=node.value.split('.')
                if len(parts)>=3 and parts[0] in needed:needed[parts[0]].add(parts[1].removesuffix('_ttm'))
            if isinstance(node,ast.Call) and len(node.args)>=2:
                a,b=node.args[:2]
                if isinstance(a,ast.Constant) and isinstance(b,ast.Constant) and a.value in needed and isinstance(b.value,str):needed[a.value].add(b.value.removesuffix('_ttm'))
    needed['fina_indicator'].update(['q_roe','q_sales_yoy','q_ocf_to_or']);needed['balancesheet'].add('acct_payable')
    q.FIN_FIELDS={ep:sorted(cols) for ep,cols in needed.items() if cols}
    table_path=OUT/'financial_pit_tables_extra.pkl'
    if not table_path.exists():pd.to_pickle(q.pit_tables(),table_path)
    fin.update(pit.snapshot(grid,stocks,table_path=table_path))
    fin['income.__quarter__.q0']=q.income_report_quarters(grid,stocks)
    if not args_cli.risk_composites:
        previous_out,previous_fields=q.OUT,q.FIN_FIELDS
        q.OUT=OUT/'surprise_lags14';q.OUT.mkdir(exist_ok=True);q.FIN_FIELDS={'income':['revenue'],'fina_indicator':['q_dtprofit']}
        try:fin.update(pit.snapshot(grid,stocks,lags=14,table_path=table_path))
        finally:q.OUT,q.FIN_FIELDS=previous_out,previous_fields
    iv=None;beta=None
    if args_cli.risk_composites:
        from quant_corpus_semantic_source9_20261012 import ivol
        iv=ivol(f)
        r=q.ratio(f['close'],q.delay(f['close']))-1
        market=pd.DataFrame(np.where(f['cap']>0,r,np.nan)).mean(axis=1).to_numpy();mf=pd.DataFrame(np.broadcast_to(market[:,None],r.shape))
        beta=q.ratio(pd.DataFrame(r).rolling(252).cov(mf).to_numpy(),mf.rolling(252).var().to_numpy())
    errors=[];rows=[]
    for script,g in eligible.groupby('builder_script',sort=True):
        try:
            module=importlib.import_module(script.split('/')[-1][:-3]);specs=module.SPECS
            if isinstance(specs,dict):raise ValueError('batch dictionary needs dedicated adapter')
            keys=[s['key'] if isinstance(s,dict) else s[0] for s in specs]
            # Every used fin key is a literal in the displayed builder source
            # or emitted by a known field dictionary. Missing fields fail
            # explicitly; no ad-hoc fallback economic values are invented.
            args=g.arguments.iloc[0];fn=getattr(module,g.adapter.iloc[0]);kwargs={'fin':fin,'cap':cap,'f':f,'pos':pos,'iv':iv[pos] if args=='fin,cap,iv' else iv,'beta':beta}
            values=fn(*[kwargs[a] for a in args.split(',')])
            if len(values)!=len(keys):raise ValueError('builder output/spec count mismatch')
            cp=len(grid)//2;short={'fin':{k:v[:cp] for k,v in fin.items()},'cap':cap[:cp],'f':{k:v[:pos[cp-1]+1] for k,v in f.items()},'pos':pos[:cp],'iv':iv[pos[:cp]] if args=='fin,cap,iv' else iv[:pos[cp-1]+1] if iv is not None else None,'beta':beta[:pos[cp-1]+1] if beta is not None else None}
            cut=fn(*[short[a] for a in args.split(',')])
            for a,b in zip(values,cut):np.testing.assert_allclose(np.asarray(a)[:cp],b,equal_nan=True,atol=1e-5,rtol=1e-5)
            for key,value in zip(keys,values):
                if key not in set(g.key):continue
                x=np.asarray(value,np.float32);old=pd.read_pickle(q.ROOT/mainmeta.loc[key,'panel_path']);oi=stocks.get_indexer(old['stocks']);v=old['panels'][key].to_numpy(np.float32)
                if x.shape!=(len(grid),len(stocks)):raise ValueError('financial output shape mismatch')
                x[n:]=np.nan;x[n:,oi]=v;x=np.where(cap>0,x,np.nan)
                result,p,d=q.evaluate(x,grid,stocks,pos,f);p.to_csv(OUT/f'{key}.periods.csv',index=False);d.to_csv(OUT/f'{key}.daily_nav.csv',index=False);pd.to_pickle(dict(key=key,dates=grid,stocks=stocks,values=x),OUT/f'{key}.history.pkl')
                rows.append(dict(key=key,historical_periods=int((p.date<formal[0]).sum()) if len(p) else 0,prefix_rebuild_passed=True,formal_saved_values_preserved=True));pd.DataFrame(rows).to_csv(OUT/'replay_audit.csv',index=False);print('FINANCIAL_REPLAYED',len(rows),key,flush=True)
        except Exception as e:
            errors.append(dict(script=script,keys=g.key.tolist(),error=str(e)[:700]));q.dump(OUT/'replay_errors.json',errors)
    q.dump(OUT/'verification.json',dict(completed=True,replayed=len(rows),errors=errors,all592_completed=False,platform_calls=0))

if __name__=='__main__':main()
