"""Validate the inventory and three independent saved-result audits."""
import ast
import hashlib
import json
from pathlib import Path
import re

OUT=Path(__file__).resolve().parent
BASE=OUT.parent


def main():
    checks=[]
    def require(ok,name):
        assert ok,name
        checks.append(name)
    def sources(rows):
        for row in rows:
            path=OUT/row['frozen_path']
            require(hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256'], 'Source '+row['path'])
    inventory=json.loads((OUT/'inventory.json').read_text())
    require(len(inventory['peers'])==50,'50 saved peers')
    require(sum(p['status']!='not_accepted' for p in inventory['peers'])==2,'Two behavioral outcomes')
    require(sum(p['status']=='not_accepted' for p in inventory['peers'])==48,'48 not accepted')
    sources([p['source'] for p in inventory['peers']])
    for p in inventory['peers']:
        for key in ('acceptance_source','refinement_source'):
            if key in p:sources([p[key]])
    sources([p['source'] for p in inventory['separate_refinements']])
    for rank in (36,8,6):
        d=json.loads((OUT/f'peer-{rank}/audit.json').read_text())
        require(d['validation']['passed'],f'Audit {rank}')
        require(d['platform_compute']==0 and not d['new_backtest'],f'No platform run {rank}')
        sources(d['sources'])
        require(all(c['metadata_active_count']==c['public_active_count'] for c in d['checks']),f'Active lifecycle {rank}')
    files=[OUT/'summary.md',BASE/'README.md',BASE/'RECONSTRUCTION_PLAYBOOK.md',
           BASE/'cases/alpha-20261015-accepted.md',BASE/'cases/alpha-20261015-closeout.md',
           BASE/'top50-20261013/README.md']
    for f in files:
        for href in re.findall(r'\[[^\]]*\]\(([^)]+)\)',f.read_text()):
            if '://' in href or href.startswith('#'):continue
            target=href.split('#')[0]
            if target:require((f.parent/target).exists(),'Link '+str(f.relative_to(BASE))+' '+href)
    for f in OUT.glob('*.py'):
        ast.parse(f.read_text());checks.append('Syntax '+f.name)
    (OUT/'validation.json').write_text(json.dumps(dict(passed=True,checks=len(checks),items=checks,
        scope='Saved evidence consistency and documentation; no new market reconstruction or untouched OOS'),ensure_ascii=False,indent=2)+'\n')
    manifest={str(f.relative_to(OUT)):hashlib.sha256(f.read_bytes()).hexdigest()
              for f in OUT.rglob('*') if f.is_file() and f.name!='manifest.json'}
    (OUT/'manifest.json').write_text(json.dumps(dict(files=manifest,platform_compute=0),ensure_ascii=False,indent=2)+'\n')
    print('Verified',len(checks),'checks;',len(manifest),'archived files')


if __name__=='__main__':main()
