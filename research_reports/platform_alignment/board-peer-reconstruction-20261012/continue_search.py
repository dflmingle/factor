"""Evaluate three score-shape candidates selected from the existing symbolic search.
No platform calls; uses the frozen alignment data and local metrics only.
"""
from __future__ import annotations
import importlib.util, json, pickle, sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
SEARCH=HERE/'search'
OUT=HERE/'continued_round1_corrected'
sys.path.insert(0,str(ROOT/'scripts'))
runner_path=HERE/'run_search.py'
spec=importlib.util.spec_from_file_location('peer_runner',runner_path)
runner=importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)

CANDIDATES={
    'LIQ_REV':'Add(lowamount20,reversal60)',
    'VOL_SIZE':'ProtectedDiv(lowvol60,smallsize)',
    'VOL_TURN':'ProtectedDiv(lowvol60,lowturn5)',
}

def main():
    protocol=json.loads((HERE/'search_protocol.json').read_text())
    market=ROOT/protocol['data']['market_cache']
    with market.open('rb') as f: calendar, stocks, fields=pickle.load(f)
    calendar=pd.DatetimeIndex(calendar); stocks=pd.Index(stocks)
    # Use precisely the same eligibility and causal price fill as run_search.
    active=np.isfinite(fields['cap']) & (fields['cap']>0) & np.isfinite(fields['turnover'])
    fields['cap'][~active]=np.nan
    for k in ('close','volume','amount'):
        fields[k][~active | (fields[k]<=0)]=np.nan
    fields['close']=pd.DataFrame(fields['close']).ffill().to_numpy(np.float32)
    OUT.mkdir(exist_ok=True)
    axes=json.loads((SEARCH/'axes.json').read_text())
    dates=pd.DatetimeIndex(axes['dates']); pos=calendar.get_indexer(dates)
    with np.load(SEARCH/'atoms.npz') as z: atoms={k:z[k] for k in z.files}
    formulas={k:runner.tree_parse(v) for k,v in CANDIDATES.items()}
    signals={k:runner.expression(t,atoms) for k,t in formulas.items()}
    targets=pd.read_csv(HERE/'factor_targets.csv')
    targets=targets[targets.period.eq('2026-10')]
    rows=[]; monthly_rows=[]
    schedules={'c3':pd.DatetimeIndex(axes['native_cycle3_dates']),'c10':pd.DatetimeIndex(axes['formal_cycle10_dates'])}
    for cycle, ds in [(3,schedules['c3']),(10,schedules['c10'])]:
        idx=dates.get_indexer(ds); p=calendar.get_indexer(ds)
        cap=fields['cap'][p]
        y=fields['close'][p+cycle+1].astype(float)/fields['close'][p+1]-1
        y[~np.isfinite(cap)]=np.nan
        windows=[('formal_5y',np.ones(len(ds),bool)),('recent_2026',ds>=pd.Timestamp('2026-01-01')),('historical_final',ds>=pd.Timestamp('2025-08-22'))]
        for name,sig in signals.items():
            x=sig[idx]
            for window,mask in windows:
                st,periods=runner.metrics(x[mask],y[mask],cap[mask],ds[mask],cycle)
                risk,daily,monthly,turns=runner.daily_path(x[mask],y[mask],cap[mask],ds[mask],calendar,fields['close'],cycle)
                complete=monthly.loc[~monthly.partial]
                mean_nc=float(complete.nc.mean()) if len(complete) else np.nan
                rows.append({'candidate':name,'formula':CANDIDATES[name],'cycle':cycle,'window':window,**st,**risk,'mean_monthly_nc':mean_nc,'months':len(complete)})
                monthly['candidate']=name; monthly['cycle']=cycle; monthly['window']=window; monthly_rows.append(monthly)
    result=pd.DataFrame(rows); result.to_csv(OUT/'results.csv',index=False)
    pd.concat(monthly_rows,ignore_index=True).to_csv(OUT/'monthly.csv',index=False)
    # Compare to the targets chosen before this round, never reselect a target
    # simply because a different public record fits the realised score better.
    formal=result[(result.cycle==3)&result.window.eq('formal_5y')].copy()
    fixed_targets={
        'LIQ_REV':('不知所云队','probe-illiquidity'),
        'VOL_SIZE':('Alpha猎手','oos-f_c_val_rev_oos'),
        'VOL_TURN':('不抵灼灼目光','19'),
    }
    scale=np.array([.02,.20,.10])
    fit=[]
    for r in formal.itertuples():
        opponent,factor=fixed_targets[r.candidate]
        t=targets[targets.display_name.eq(opponent)&targets.factor_name.eq(factor)].iloc[0]
        x=np.array([r.rank_ic,r.rank_ir,r.rank_win]); target=np.array([t.ic_mean,t.icir,t.ic_win_rate])
        dist=float(np.mean(((x-target)/scale)**2))
        fit.append({'candidate':r.candidate,'formula':r.formula,'closest_opponent':t.display_name,'closest_factor':t.factor_name,'public_ic':t.ic_mean,'public_ir':t.icir,'public_win':t.ic_win_rate,'local_ic':r.rank_ic,'local_ir':r.rank_ir,'local_win':r.rank_win,'delta_ic':r.rank_ic-t.ic_mean,'delta_ir':r.rank_ir-t.icir,'delta_win':r.rank_win-t.ic_win_rate,'score_distance':dist,'public_s_i':t.s_i_a,'s_i':r.s_i,'delta_s_i':r.s_i-t.s_i_a,'mean_monthly_nc':r.mean_monthly_nc,'net_excess':r.net_excess,'turnover':r.turnover,'max_dd':r.daily_net_nav_max_dd})
    fit=pd.DataFrame(fit); fit.to_csv(OUT/'target_fit.csv',index=False)
    lines=['# 继续搜索的三条候选（2026-10-12）','', '本轮从既有符号搜索中挑出三条未冻结结构，做完整本地复核；平台调用 0 次。','', '|候选|公式|最近公开目标|RankIC差|IR差|胜率差|距离|S_i|单因子月均NC|净超额|换手|最大回撤|','|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in fit.itertuples():
        lines.append(f'|{r.candidate}|`{r.formula}`|{r.closest_opponent}/{r.closest_factor}|{r.delta_ic:+.4f}|{r.delta_ir:+.4f}|{r.delta_win:+.1%}|{r.score_distance:.4f}|{r.s_i:.4f}|{r.mean_monthly_nc:.3f}|{r.net_excess:.2%}|{r.turnover:.2%}|{r.max_dd:.2%}|')
    lines += ['', '上表仅为固定目标的单因子诊断，未恢复整池。原结果遗漏行情有效性过滤与前向填充，现按原搜索口径纠正；不覆盖旧输出。',
              '本地数据截止2026-09-07，公开评分来自9月结算/10月预估，缺少同月市场行情与逐席位样本外序列；NB/NC/comb 的对手差值均未计算，不能用五年月均NC作当月NC。',
              '先前只替换A、保留对手B/C所产生的总分接近不构成复刻证据。',
              '结果见 results.csv、monthly.csv、target_fit.csv；本轮三条均不满足完整因子池复刻目标。']
    (OUT/'summary.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(f'completed {len(result)} rows, {len(fit)} target fits')

if __name__=='__main__': main()
