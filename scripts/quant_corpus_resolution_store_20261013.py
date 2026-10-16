"""Append auditable precise resolutions while preserving previous registries."""
import ast,hashlib,json
from collections import defaultdict
import pandas as pd
import quant_corpus_local_20261012 as q
from quant_strategy_factor_catalog_20261012 import read_text
from quant_corpus_dependency_resolutions10_20261013 import StripDoc
CAT=q.ROOT/'research_reports/literature/quant-corpus-factor-catalog-20261012'
OUT=CAT/'exhaustive_sweep_20261013'

class Store:
 def __init__(self,number):
  self.number=number;self.rows=json.loads((OUT/'precise_source_resolutions.json').read_text())
  self.eout=OUT/f'dependency_source_evidence{number}';self.eout.mkdir(exist_ok=True)
  prior=self.eout/'registry_before.json'
  if not prior.exists():q.dump(prior,self.rows)
 def find(self,folder,pat):
  paths=list((q.ROOT/folder).glob(pat));assert len(paths)==1,(folder,pat,paths)
  return str(paths[0].relative_to(q.ROOT))
 def save(self,path,state,decision,anchors=(),keys=(),extra=None):
  p=q.ROOT/path;s=read_text(p);ev=[]
  for a in anchors:
   found=[dict(line=i+1,text=l.strip()[:500]) for i,l in enumerate(s.splitlines()) if ''.join(a.split()) in ''.join(l.split())];assert found,(path,a);ev+=found[:4]
  sha=hashlib.sha256(p.read_bytes()).hexdigest();ep=self.eout/(sha+'.source.txt');ep.write_text(s)
  self.rows[:]=[r for r in self.rows if r['path']!=path]
  self.rows.append(dict(path=path,sha256=sha,resolution=state,decision=decision,evidence=ev,related_tested_keys=list(keys),full_strategy_reproduced=False,decoded_evidence=str(ep.relative_to(q.ROOT)),**(extra or {})))
 def aliases(self):
  coverage=pd.read_csv(OUT/'all_source_coverage.csv').fillna('');buckets=defaultdict(list)
  for r in coverage.to_dict('records'):
   p=q.ROOT/r['path']
   if p.suffix.lower() not in ['.py','.txt','.ipynb']:continue
   try:tree=ast.parse(read_text(p).split('原文策略源码如下：',1)[-1].expandtabs(4))
   except SyntaxError:continue
   sha=hashlib.sha256(ast.dump(StripDoc().visit(tree),include_attributes=False).encode()).hexdigest();buckets[sha].append(r)
  resolved={r['path']:r for r in self.rows};aliases=[]
  for sha,group in buckets.items():
   prior=[r for r in group if r['path'] in resolved]
   if not prior:continue
   canonical=prior[0];cr=resolved[canonical['path']];keys=cr['related_tested_keys']
   for r in group:
    if r['path'] in resolved or r['actual_recipe_links'] or r['path']==canonical['path']:continue
    if r['sweep_state'] not in ['reviewed_family_duplicate_or_variant_needs_recipe_trace','reviewed_dependency_or_applicability_blocker']:continue
    self.save(r['path'],'tested_atom_with_complete_executable_AST_alias' if keys else 'missing_dependencies_complete_executable_AST_alias',
     '完整可执行AST只去独立字符串后相同；继承 '+canonical['path']+' 的精确已测原子与所有未复现层，不是完整收益认证。'+cr['decision'],keys=keys,
     extra=dict(equivalent_source=canonical['path'],full_executable_ast_sha256=sha,normalization='standalone string Expr only'))
    aliases.append(dict(path=r['path'],canonical=canonical['path'],keys=keys))
  q.dump(self.eout/'new_exact_whole_AST_aliases.json',aliases)
  return aliases
 def commit(self):
  q.dump(OUT/'precise_source_resolutions.json',self.rows)
  pd.DataFrame([{**r,'evidence':json.dumps(r['evidence'],ensure_ascii=False),'related_tested_keys':';'.join(r['related_tested_keys'])} for r in self.rows]).to_csv(OUT/'precise_source_resolutions.csv',index=False)
  q.dump(OUT/'precise_resolution_state.json',dict(records=len(self.rows),source_hashes_unchanged=True,all_corpus_complete=False))
  print('PRECISE_SOURCE_RESOLUTIONS',len(self.rows),flush=True)
