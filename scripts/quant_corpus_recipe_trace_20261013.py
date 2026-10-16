"""Exact source-function traces and concrete blockers; not title-based completion."""
import ast,hashlib,json,re
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq
import quant_corpus_local_20261012 as q
from quant_strategy_factor_catalog_20261012 import read_text
CAT=q.ROOT/'research_reports/literature/quant-corpus-factor-catalog-20261012'
OUT=CAT/'exhaustive_sweep_20261013'

def units(text):
 # Function-local AST permits prose before code and notebook magic elsewhere.
 lines=text.splitlines();starts=[i for i,l in enumerate(lines) if re.match(r'^def\s+\w+\(',l)]
 result=[]
 for n,a in enumerate(starts):
  b=starts[n+1] if n+1<len(starts) else len(lines);block='\n'.join(lines[a:b]);match=re.match(r'def\s+(\w+)',block);name=match.group(1)
  # Only remove tail non-code comments/prose; preserve literals/operators.
  for trim in range(0,min(16,b-a)):
   part='\n'.join(lines[a:b-trim])
   try:
    tree=ast.parse(part)
    defs=[x for x in tree.body if isinstance(x,ast.FunctionDef)]
    if len(defs)!=1:continue
    fn=defs[0];key=ast.dump(fn,include_attributes=False);result.append(dict(name=name,line=a+1,end=a+fn.end_lineno,ast_sha256=hashlib.sha256(key.encode()).hexdigest()));break
   except SyntaxError:continue
 return result

def main():
 OUT.mkdir(exist_ok=True);source=json.loads((CAT/'source_review.json').read_text());tested={}
 for p in (q.ROOT/'research_reports/platform_alignment').glob('quant-corpus*/recipe_manifest.json'):
  rows=json.loads(p.read_text())
  if not isinstance(rows,list):continue
  for r in rows:
   for s in r.get('source_paths',[]):tested.setdefault(s,[]).append(f"{p.parent.name}:{r['key']}")
 indexed=[];byhash={};readrows=[]
 for row in source:
  p=q.ROOT/row['path']
  if p.suffix.lower() not in ['.txt','.py','.ipynb']:continue
  text=read_text(p);sha=hashlib.sha256(p.read_bytes()).hexdigest();assert sha==row['sha256']
  funcs=units(text);readrows.append(dict(path=row['path'],sha256=sha,decoded_characters=len(text),source_review_level=row['review_level'],function_units=len(funcs),interpretation='mechanical exact trace supplements prior semantic review; does NOT prove new semantic/fullstrategy review'))
  for u in funcs:
   u.update(path=row['path'],source_sha256=sha,tested_source_links=';'.join(tested.get(row['path'],[])));indexed.append(u);byhash.setdefault(u['ast_sha256'],[]).append(u)
 links=[]
 # Matching one utility does not resolve the entire strategy. Never change
 # per-source tested/completed state from these links alone.
 for u in indexed:
  if u['path'] in tested:continue
  peers=[v for v in byhash[u['ast_sha256']] if v['path'] in tested]
  for v in peers[:3]:links.append(dict(path=u['path'],function=u['name'],line=u['line'],ast_sha256=u['ast_sha256'],reference_path=v['path'],reference_line=v['line'],tested_source_links=v['tested_source_links'],scope='exact function only; parameters/callpath/gates/execution remain tocheck'))
 pd.DataFrame(indexed).to_csv(OUT/'source_function_units.csv',index=False)
 pd.DataFrame(links).to_csv(OUT/'exact_function_recipe_traces.csv',index=False)
 pd.DataFrame(readrows).to_csv(OUT/'decoded_source_trace_inventory.csv',index=False)
 cache=q.CACHE;proof={'cache_root':str(cache.relative_to(q.ROOT)),'market_calendar_rows':len(q.load_market()[0]),'missing_daily_datasets':{},'financial_asof_history':{},'binary':{}}
 for ep in ['fina_indicator','income','balancesheet','cashflow']:
  tables=[]
  for p in (cache/'financial_full_a'/ep).glob('*.parquet'):
   names=pq.ParquetFile(p).schema_arrow.names;cols=[c for c in ['ann_date','f_ann_date','end_date'] if c in names];tables.append(pd.read_parquet(p,columns=cols))
  t=pd.concat(tables,ignore_index=True);date=pd.to_datetime(t.ann_date,errors='coerce')
  if 'f_ann_date' in t:date=pd.concat([date,pd.to_datetime(t.f_ann_date,errors='coerce')],axis=1).max(axis=1)
  proof['financial_asof_history'][ep]=dict(min_actual_announcement=str(date.min()),min_report_date=str(pd.to_datetime(t.end_date,errors='coerce').min()),rows=int(len(t)))
 for dataset in ['index_daily','etf_daily','stk_limit','dividend','fina_audit','northbound','longhu','historical_industry']:
  matches=[str(p.relative_to(cache)) for p in cache.rglob('*') if p.is_dir() and dataset in p.name]
  proof['missing_daily_datasets'][dataset]=dict(matching_cache_directories=matches,present=bool(matches),search='directory inventory; field absence supported separately by schemas, not a global assertion no other machine data exists')
 binaries=[q.ROOT/r['path'] for r in source if str(r['path']).endswith('.rzrk')]
 proof['binary']=dict(files=len(binaries),header_sha256=[hashlib.sha256(p.read_bytes()[:64]).hexdigest() for p in binaries[:3]],decoded=False)
 q.dump(OUT/'data_applicability_evidence.json',proof)
 q.dump(OUT/'exact_trace_completion.json',dict(completed=True,decoded_texts=len(readrows),exact_function_links=len(links),sources_with_links=len(set(x['path'] for x in links)),semantic_completion_inferred=False,full_corpus_reproduction_complete=False,platform_compute=0))
 print('TRACE_COMPLETE',len(readrows),len(indexed),len(links),flush=True)
if __name__=='__main__':main()
