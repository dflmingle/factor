#!/usr/bin/env python3
"""Automatically finish the expanded matched study from completed replays."""
import subprocess,sys,time,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research_reports/platform_alignment/regime-long-history-20261014'

def main():
    required=[ROOT/'research_reports/platform_alignment/shu-mulvey-long-base-20261014/verification.json',ROOT/'research_reports/platform_alignment/regime-long-market-replay-20261014/verification.json',ROOT/'research_reports/platform_alignment/regime-long-financial-replay-v2-20261014/verification.json']
    state=OUT/'extended_pipeline_status.json'
    state.write_text(json.dumps(dict(stage='waiting_for_replays_and_base_comparison',completed=False),indent=2)+'\n')
    while not all(p.exists() and json.loads(p.read_text()).get('completed') for p in required):time.sleep(10)
    # Rerun the market adapter after its initial completion to pick up the
    # explicit warmup fix and core IVOL source adapter. Existing files reused.
    for stage,command in [('market_warmup_adapters',[sys.executable,str(ROOT/'scripts/regime_long_market_replay_20261014.py')]),('expanded_matched_sjm',[sys.executable,str(ROOT/'scripts/shu_mulvey_long_base_20261014.py'),'--include-market']),('report',[sys.executable,str(ROOT/'scripts/regime_long_report_20261014.py')])]:
        state.write_text(json.dumps(dict(stage=stage,completed=False),indent=2)+'\n')
        with (OUT/f'{stage}.log').open('a') as log:result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        if result.returncode:
            state.write_text(json.dumps(dict(stage=stage,completed=False,failed=True),indent=2)+'\n');raise RuntimeError(f'{stage} failed')
        print('EXTENDED_PIPELINE_COMPLETED',stage,flush=True)
    state.write_text(json.dumps(dict(stage='finished',completed=True,all592_completed=False),indent=2)+'\n')

if __name__=='__main__':main()
