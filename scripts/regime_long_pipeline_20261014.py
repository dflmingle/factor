#!/usr/bin/env python3
"""Continue authorized offline research after the resumable fetch completes."""
import json, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research_reports/platform_alignment/regime-long-history-20261014'

def main():
    state=OUT/'pipeline_status.json'
    steps=[('financial_audit','regime_long_financial_audit_20261014.py'),('assemble','regime_long_history_data_20261014.py'),('base_replay','regime_long_base_replay_20261014.py'),('matched_sjm','shu_mulvey_long_base_20261014.py'),('market_replay','regime_long_market_replay_20261014.py')]
    state.write_text(json.dumps(dict(stage='waiting_for_complete_download',completed=False),indent=2)+'\n')
    while True:
        p=json.loads((OUT/'download_progress.json').read_text())
        if p.get('stage')=='finished':
            if not p.get('completed'):raise RuntimeError('Download has unresolved errors; pipeline stopped')
            break
        time.sleep(10)
    completed=[]
    for stage,script in steps:
        state.write_text(json.dumps(dict(stage=stage,completed=False,completed_steps=completed),indent=2)+'\n')
        log=OUT/f'{stage}.log'
        with log.open('a') as file:
            result=subprocess.run([sys.executable,str(ROOT/'scripts'/script)],cwd=ROOT,stdout=file,stderr=subprocess.STDOUT)
        if result.returncode:
            state.write_text(json.dumps(dict(stage=stage,completed=False,failed=True,log=str(log.relative_to(ROOT)),completed_steps=completed),indent=2)+'\n')
            raise RuntimeError(f'{stage} failed: {log}')
        completed.append(stage);print('PIPELINE_COMPLETED',stage,flush=True)
    state.write_text(json.dumps(dict(stage='finished',completed=True,completed_steps=completed,all592_completed=False),indent=2)+'\n')

if __name__=='__main__':main()
