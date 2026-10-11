"""Run refinement, independent audit, and report once training is complete."""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research_reports/platform_alignment/fengmao-rankboost-round2-20261011'


def main():
    deadline=time.monotonic()+3600
    while not (OUT/'metadata.json').exists():
        if (OUT/'memory_stop.json').exists():
            raise RuntimeError('Upstream memory boundary stop; no postprocessing')
        if time.monotonic()>deadline:
            raise TimeoutError('Upstream training did not complete within one hour')
        time.sleep(5)
    assert json.loads((OUT/'metadata.json').read_text(encoding='utf8'))['status']=='complete'
    commands=[('refinement.json','refine_fengmao_rankboost_round2_20261011.py'),
              ('verification.json','verify_fengmao_rankboost_round2_20261011.py'),
              ('summary.md','report_fengmao_rankboost_round2_20261011.py')]
    for artifact,script in commands:
        if (OUT/artifact).exists():
            continue
        print('POSTPROCESS',script,flush=True)
        subprocess.run([sys.executable,str(ROOT/'scripts'/script)],cwd=ROOT,check=True)
    print('FIT REFINEMENT, INDEPENDENT AUDIT, AND REPORT COMPLETE',flush=True)


if __name__=='__main__':
    main()
