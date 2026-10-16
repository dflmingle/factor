"""Explicit no-worsening guard on the large per-seat A discrepancies.

The search's composite fit is exploratory. This second, reported acceptance
gate prevents a better IC at one seat from excusing a worse A there.
"""
import json
import math
from pathlib import Path

OUT=Path(__file__).resolve().parent


def main():
    r=json.loads((OUT/'result.json').read_text());bank=json.loads((OUT/'candidate_bank.json').read_text())
    baseline=r['baselines'][0];focus=[0,2,7,8]
    def error(b):return abs(math.log(bank[b]['A']['2026-10']['local']['s_i_a']/bank[b]['A']['2026-10']['public']['s_i_a']))
    kept=[];rejected=[]
    candidates=r['finalists']+[baseline]
    for row in candidates:
        regressions=[j+1 for j in focus if error(row['state'][j])>error(baseline['state'][j])+1e-12]
        if regressions:
            rejected.append(dict(state=row['state'],A_regression_seats=regressions));continue
        kept.append(row)
    kept.sort(key=lambda row:(sum(error(row['state'][j])**2 for j in focus),
        sum(bank[row['state'][j]]['seat_loss'] for j in focus),row['loss']))
    selected=kept[0]
    out=dict(r,selected=selected,selected_seats=[bank[b] for b in selected['state']],
        acceptance=dict(source='top20 combinations retained by search plus baseline; not exhaustive',
            gate='absolute log A error cannot worsen at any of seats 1,3,8,9',
            candidates=len(candidates),kept=len(kept),rejected=rejected,
            baseline_replaced=False,original_search_selected=r['selected']['state']))
    (OUT/'accepted_result.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    manifest=dict(formula_trees=[s['tree'] for s in out['selected_seats']],legs=out['selected_seats'],
        directions=[-1,-1,-1,-1,1,-1,-1,-1,-1,1],equal_pool_weights=True,
        rule_reference=r['protocol']['rule_reference'],all_dates_fitted=True,strict_oos=False,
        platform_confirmed=False,platform_compute=0,baseline_replaced=False,status='local_verification_pending')
    (OUT/'candidate_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(selected=selected['state'],baseline=baseline['state'],kept=len(kept),
        all_four_A_not_worse=True,path=[p['top20'] for p in selected['path']])))


if __name__=='__main__':main()
