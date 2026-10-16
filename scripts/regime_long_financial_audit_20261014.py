#!/usr/bin/env python3
"""Audit historical filing coverage and explicit field availability."""
import pandas as pd
import numpy as np
import regime_long_history_data_20261014 as data
import quant_corpus_local_20261012 as q

def main():
    rows=[];coverage=[];errors=[];quarantine=[]
    for ep,wanted in q.FIN_FIELDS.items():
        for period in pd.period_range('2006Q1','2017Q4',freq='Q'):
            path=data.DATA/'financial_full_fields_v2'/ep/f'period_{period.end_time:%Y%m%d}.parquet'
            if not path.exists():errors.append(f'missing {ep} {period}');continue
            frame=pd.read_parquet(path)
            a=pd.to_datetime(frame.ann_date,errors='coerce')
            if 'f_ann_date' in frame:a=pd.concat([a,pd.to_datetime(frame.f_ann_date,errors='coerce')],axis=1).max(axis=1)
            end=pd.to_datetime(frame.end_date,errors='coerce')
            invalid=int((a<end).sum());missing=sorted(set(wanted)-set(frame))
            if missing:errors.append(dict(endpoint=ep,period=str(period),missing_fields=missing))
            bad=(a<end)|a.isna()|end.isna()
            for _,r in frame.loc[bad].iterrows():quarantine.append(dict(endpoint=ep,period=str(period),ts_code=r.ts_code,ann_date=r.ann_date,end_date=r.end_date,reason='invalid announcement chronology or missing date'))
            target=data.DATA/'financial_pit_validated_v3'/ep/path.name;target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():
                if bad.any():frame.loc[~bad].to_parquet(target,index=False)
                else:target.symlink_to(path.resolve())
            keys=['ts_code','ann_date','end_date'];duplicates=frame.duplicated(keys,keep=False)
            # update_flag variants can be identical in all actual fields.
            cols=[c for c in wanted if c in frame]
            groups=frame.loc[duplicates].groupby(keys)[cols].nunique(dropna=False)
            conflict=int((groups.max(axis=1)>1).sum()) if len(groups) else 0
            rows.append(dict(endpoint=ep,period=str(period),rows=len(frame),symbols=frame.ts_code.nunique(),first_announcement=str(a.min().date()),last_announcement=str(a.max().date()),missing_announcement_rows=int(a.isna().sum()),announcements_before_period_end=invalid,duplicate_key_rows=int(duplicates.sum()),duplicate_key_field_conflicts=conflict,missing_expected_fields=';'.join(missing)))
            for col in wanted:
                coverage.append(dict(endpoint=ep,period=str(period),field=col,rows=len(frame),finite_rows=int(pd.to_numeric(frame[col],errors='coerce').notna().sum()) if col in frame else 0))
    pd.DataFrame(rows).to_csv(data.OUT/'historical_financial_period_audit.csv',index=False)
    pd.DataFrame(coverage).to_csv(data.OUT/'historical_financial_field_coverage.csv',index=False)
    pd.DataFrame(quarantine).to_csv(data.OUT/'financial_quarantined_rows.csv',index=False)
    q.dump(data.OUT/'financial_verification.json',dict(completed=not errors,quarters=48,endpoints=4,files=len(rows),errors=errors,quarantined_rows=len(quarantine),validated_view='financial_pit_validated_v3; raw snapshots preserved',announcement_connection='max(ann_date,f_ann_date); invalid dates excluded; no backward-fill',revision_limitation='vendor historical fields and same-announcement update variants lack original release versions; PIT reconstruction remains a proxy',duplicates='existing contract sorts update_flag, keeps last key; conflicts explicitly counted; not interpreted as new independent observations',missing_economic_values='keep NaN; field availability does not imply finite coverage'))
    if errors:raise RuntimeError('Financial history audit has errors; inspect verification')
    print('FINANCIAL_AUDIT_COMPLETE',len(rows),flush=True)

if __name__=='__main__':main()
