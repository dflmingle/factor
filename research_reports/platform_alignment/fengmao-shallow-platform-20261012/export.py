"""Export the frozen original model; never fit or change its parameters."""
import hashlib
import json
import re
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
SOURCE=ROOT/'research_reports/platform_alignment/fengmao-nested-causal-20261011'

def main():
    meta=next(m for m in json.loads((SOURCE/'frozen_candidates.json').read_text())['candidates'] if m['family']=='shallow')
    model=SOURCE/'FM_CAUSAL_SHALLOW.txt';content=model.read_text()
    chunks=re.split(r'\nTree=\d+\n',content)[1:]
    trees=[];used=set()
    for chunk in chunks:
        d=dict(re.findall(r'^([a-z_]+)=(.*)$',chunk,re.M))
        assert d['num_leaves']=='3' and d['decision_type']=='2 2'
        features=list(map(int,d['split_feature'].split()));used.update(features)
        trees.append((features,list(map(float,d['threshold'].split())),list(map(int,d['left_child'].split())),list(map(int,d['right_child'].split())),list(map(float,d['leaf_value'].split()))))
    assert len(trees)==200 and len(meta['features'])==60 and len(used)==32
    def expression(tree,node=0):
        feat,threshold,left,right,leaf=tree
        if node<0:return repr(leaf[-node-1])
        # LightGBM compares float32 inputs against float64 thresholds. Force
        # the comparison precision without rounding a threshold to float32.
        return "np.where(np.less_equal(x[%r], %r, signature='dd->?'), %s, %s)"%(meta['features'][feat[node]],threshold[node],expression(tree,left[node]),expression(tree,right[node]))
    src=(HERE/'template.py.txt').read_text()
    body=['def _predict(x):','    first = next(iter(x.values()))','    value = np.zeros(first.shape, dtype=np.float64)']
    body += ['    value += '+expression(t) for t in trees]
    body += ['    return value.astype(np.float32)','']
    src=src.replace('PREDICT_PLACEHOLDER','\n'.join(body))
    (HERE/'candidate.py').write_text(src)
    manifest={'name':'Q131-20261012','source_model':str(model.relative_to(ROOT)),'source_sha256':hashlib.sha256(model.read_bytes()).hexdigest(),'candidate_sha256':hashlib.sha256(src.encode()).hexdigest(),'registered_features':meta['features'],'used_features':[meta['features'][i] for i in sorted(used)],'trees':200,'leaves':3,'direction':1,'training_cutoff':'2025-08-22','training_warning':'Five-year diagnostics include training observations; only post-training dates are temporally valid frozen predictions. Historical holdout was previously viewed.','platform_request':{'start':'20210907','end':'20260907','cycle':10,'groups':10,'one_way_cost':.003},'no_refit':True,'no_new_features':True}
    (HERE/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    (HERE/'candidates.txt').write_text('# Frozen original shallow model; one five-year alignment candidate.\nQ131-20261012 ~ candidate.py ~ 1\n')
    print('exported frozen200 trees,32 used inputs; original60-feature contract')

if __name__=='__main__':main()
