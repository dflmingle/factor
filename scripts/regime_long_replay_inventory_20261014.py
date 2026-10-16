#!/usr/bin/env python3
"""Map every canonical factor to its historical replay code, without running it."""
import ast, json
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research_reports/platform_alignment/regime-long-history-20261014'
META=ROOT/'research_reports/platform_alignment/shu-mulvey-sjm-bl-20261014/factor_metadata.csv'

def main():
    scripts=[]
    for p in sorted((ROOT/'scripts').glob('quant_corpus_*.py')):
        tree=ast.parse(p.read_text())
        functions={n.name:[a.arg for a in n.args.args] for n in tree.body if isinstance(n,ast.FunctionDef)}
        strings={n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str)}
        folders={s for s in strings if s.startswith('research_reports/platform_alignment/')}
        scripts.append((p,functions,strings,folders))
    rows=[]
    for _,r in pd.read_csv(META).iterrows():
        folder=str(Path(r.panel_path).parent)
        matches=[(p,f) for p,f,s,d in scripts if folder in d]
        if not matches:matches=[(p,f) for p,f,s,d in scripts if r.key in s]
        adapter='manual_adapter_required';selected='';args=[]
        if r.key.startswith('candle_'):
            adapter='safe_talib_calculate';selected='scripts/quant_corpus_candles_20261013.py';args=['name','f']
        elif folder.endswith('quant-corpus-source-reproduction-20261012'):
            adapter='base_generators';selected='scripts/quant_corpus_local_20261012.py'
        else:
            for p,f in matches:
                for name in ['values','build','recipe','kernels','make_scores','predict','one']:
                    if name in f:
                        selected=str(p.relative_to(ROOT));adapter=name;args=f[name];break
                if selected:break
            if not selected and matches:selected=str(matches[0][0].relative_to(ROOT))
        rows.append(dict(key=r.key,name=r['name'],panel_path=r.panel_path,builder_script=selected,adapter=adapter,arguments=','.join(args),
                         formula=r.formula,fidelity=r.fidelity,
                         replay_status='not_yet_replayed',reason='needs historical rebuild and saved-panel alignment check',
                         data_ready=False,formal_panel_preservation='use original saved formal panel; rebuild historical prefix independently'))
    frame=pd.DataFrame(rows);OUT.mkdir(parents=True,exist_ok=True);frame.to_csv(OUT/'all_factor_replay_inventory.csv',index=False)
    (OUT/'replay_coverage.json').write_text(json.dumps(dict(total_canonical_main_factors=len(frame),mapped_builder_scripts=int(frame.builder_script.ne('').sum()),historical_replays_completed=0,all_factors_long_models_completed=False,adapter_counts=frame.adapter.value_counts().to_dict(),selection='all592, no performance screen'),ensure_ascii=False,indent=2)+'\n')
    print(frame.adapter.value_counts().to_string());print('TOTAL',len(frame),'MAPPED',frame.builder_script.ne('').sum(),flush=True)

if __name__=='__main__':main()
