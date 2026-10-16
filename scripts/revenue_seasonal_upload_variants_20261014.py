"""Export two previously tested accounting controls, never using forward labels."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
from pathlib import Path
import hashlib
import numpy as np
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_corpus_continue_20261013 import simultaneous_residual

OUT=q.ROOT/'research_reports/platform_alignment/revenue-seasonal-platform-20261014'
BASE=q.ROOT/'research_reports/platform_alignment/quant-corpus-accounting-completion-20261014'
DEFS=[('control3','F-Q141014-07','size_reversal_IVOL_residual',3),
      ('control6','F-Q141014-08','size_rev_IVOL_ROE_BM_profitgrowth_residual',6)]

def main():
    cal,stocks,f=q.load_market()
    dates=cal[(cal>='20210907')&(cal<='20260907')];pos=cal.get_indexer(dates)
    signal=pd.read_pickle(BASE/'daily_scores.pkl')['coherent_seasonal_revenue_sue3']
    iv=pd.read_pickle(q.ROOT/'research_reports/platform_alignment/quant-corpus-semantic-source9-20261012/ivol_daily.pkl')
    controls=[-f['cap'][pos],-(q.ratio(f['close'],q.delay(f['close'],20))-1)[pos],-iv[pos]]
    for ep,col in [('fina_indicator','roe'),('balancesheet','total_hldr_eqy_exc_min_int'),('fina_indicator','netprofit_yoy')]:
        v=q.daily_pit_field(ep,col,cal,stocks)[pos].copy()
        if ep=='balancesheet':v=q.ratio(v,f['cap'][pos]*10000)
        v[~(f['cap'][pos]>0)]=np.nan
        controls.append(v)
    saved=pd.read_pickle(BASE/'signal_panels.pkl');grid=saved['dates'];ix=dates.get_indexer(grid)
    old=pd.read_pickle(q.OUT/'signal_panels.pkl')['panels']
    expected=[-f['cap'][cal.get_indexer(grid)],controls[1][ix],-iv[cal.get_indexer(grid)]]
    expected +=[old[k].reindex(index=grid,columns=stocks).to_numpy() for k in ['roe','book_market','growth_profit']]
    checks=[];exports=[];uploaded_parts=[]
    for label,name,form,n in DEFS:
        v=simultaneous_residual(signal,controls[:n])
        ref=simultaneous_residual(saved['panels']['coherent_seasonal_revenue_sue3'].to_numpy(),expected[:n])
        np.testing.assert_allclose(v[ix],ref,equal_nan=True,atol=1e-4,rtol=1e-5)
        checks.append(dict(label=label,test='previous_local_recipe_signal_grid_parity',passed=True))
        for stop in [401,901]:
            prefix=simultaneous_residual(signal[:stop],[a[:stop] for a in controls[:n]])
            np.testing.assert_allclose(v[:stop],prefix,equal_nan=True,atol=0,rtol=0)
            checks.append(dict(label=label,test='cross_sectional_prefix_recompute',stop=stop,passed=True))
        rows,cols=np.where(np.isfinite(v));file=OUT/f'seasonal_revenue_{label}_daily.parquet'
        table=pd.DataFrame({'date':dates.to_numpy()[rows],'symbol':stocks.to_numpy()[cols],'value':v[rows,cols]})
        table.to_parquet(file,index=False,compression='zstd')
        # The gateway rejects ~24 MB files although the UI advertises 100 MB.
        # Split storage only, retaining every float32 signal exactly.
        parts=[]
        for part,ids in enumerate(np.array_split(np.arange(len(table)),4)):
            namepart=f'seasonal_revenue_{label}_part{part}.parquet'
            target=OUT/namepart;table.iloc[ids].to_parquet(target,index=False,compression='zstd')
            parts.append(namepart)
            uploaded_parts.append(dict(file=namepart,sha256=hashlib.sha256(target.read_bytes()).hexdigest(),bytes=target.stat().st_size))
        pd.testing.assert_frame_equal(table,pd.concat([pd.read_parquet(OUT/a) for a in parts],ignore_index=True))
        q.dump(OUT/f'budget14-{label}-parts.json',parts)
        source=(OUT/'upload_seasonal.py').read_text().replace('seasonal_revenue_pit_daily.parquet',file.name).replace('UploadedSeasonalRevenue',f'UploadedSeasonalRevenue{n}Controls')
        source=source.replace(f"table = pd.read_parquet(upload_path('uploads/{file.name}'))",
            "table = pd.concat([pd.read_parquet(upload_path(name)) for name in "+repr(['uploads/'+a for a in parts])+"], ignore_index=True)")
        (OUT/f'upload_{label}.py').write_text(source)
        (OUT/f'budget14-{label}-candidates.txt').write_text(f'{name} ~ upload_{label}.py ~ 1\n')
        exports.append(dict(label=label,name=name,form=form,file=file.name,rows=len(rows),bytes=file.stat().st_size,sha256=hashlib.sha256(file.read_bytes()).hexdigest(),controls=n))
        print(label,len(rows),file.stat().st_size,flush=True)
    q.dump(OUT/'budget14-variants-verification.json',dict(checks=checks,exports=exports,
        multipart_storage_exact_dataframe_parity=True,uploaded_parts=uploaded_parts,
        financial_source='Tushare PIT proxy',time_standardization='none; per-date simultaneous rank regression',
        alpha_claim='exposure controls; not exact top-bucket size neutrality, not untouched OOS',forward_labels_exported=False))

if __name__=='__main__':main()
