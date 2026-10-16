#!/usr/bin/env python3
"""Render source logic for review and preserve individually authored decisions.

Rendering does not mark a strategy reviewed. Review notes must be authored after
reading the rendered core and opening the original whenever it is incomplete.
"""
import argparse
import ast
import hashlib
import json
import re
from pathlib import Path
import pandas as pd
from quant_strategy_factor_catalog_20261012 import read_text, ROOT

DEST=ROOT/'research_reports/literature/quant-corpus-factor-catalog-20261012'
NOTES=DEST/'semantic_reviews.json'
OPERATIONAL={'set_benchmark','set_option','set_slippage','set_order_cost','set_commission','set_subportfolios','send_message','record','print','display','show','savefig'}

def core(path, known_functions=None):
    text=read_text(path)
    code=text.split('原文策略源码如下：',1)[-1].expandtabs(4)
    try:tree=ast.parse(code)
    except SyntaxError:
        try:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter('ignore',DeprecationWarning)
                from lib2to3.refactor import RefactoringTool
                converted=str(RefactoringTool(['lib2to3.fixes.fix_ne','lib2to3.fixes.fix_print','lib2to3.fixes.fix_except','lib2to3.fixes.fix_numliterals']).refactor_string(code+'\n',str(path)))
            tree=ast.parse(converted)
        except Exception:
            # Keep original logic; do not infer a decision from a keyword scan.
            return 'PARSE_FAILED: READ_ORIGINAL\n'+'\n'.join(line for line in code.splitlines() if line.strip())
    class Presentation(ast.NodeTransformer):
        def visit_Expr(self,node):
            # Docstrings and prose are retained in the original linked file;
            # executable expressions and all formula constants stay visible.
            if isinstance(node.value,ast.Constant) and isinstance(node.value.value,str):return None
            if isinstance(node.value,ast.Call):
                f=node.value.func
                if isinstance(f,ast.Name) and f.id in OPERATIONAL:return None
                if isinstance(f,ast.Attribute) and (isinstance(f.value,ast.Name) and f.value.id in {'log','plt','axes','ax'}):return None
            return self.generic_visit(node)
        def visit_Assign(self,node):
            self.generic_visit(node)
            # Only fixed symbol/contract maps may be abbreviated. Numeric
            # weights or embedded training data remain visible for review.
            literal=node.value
            strings=(literal.keys+literal.values if isinstance(literal,ast.Dict)
                     else literal.elts if isinstance(literal,(ast.List,ast.Tuple)) else [])
            symbol_map=bool(strings) and all(isinstance(x,ast.Constant) and isinstance(x.value,str)
                and re.fullmatch(r'(?:\d{6}\.(?:XSHG|XSHE|SH|SZ)|[A-Za-z]+\d*\.(?:XDCE|XSGE|XZCE|CCFX|DCE|SHFE|CZCE))',x.value)
                for x in strings)
            if symbol_map and len(ast.unparse(literal))>1000:
                count=len(node.value.keys) if isinstance(node.value,ast.Dict) else len(node.value.elts)
                node.value=ast.Constant(value=f'FIXED_LITERAL_{count}_ITEMS_SEE_ORIGINAL')
            return node
        def visit_FunctionDef(self,node):
            self.generic_visit(node)
            if not node.body:node.body=[ast.Pass()]
            return node
        def visit_If(self,node):
            self.generic_visit(node)
            if not node.body:node.body=[ast.Pass()]
            return node
        def visit_For(self,node):
            self.generic_visit(node)
            if not node.body:node.body=[ast.Pass()]
            return node
    tree=Presentation().visit(tree)
    for node in ast.walk(tree):
        if hasattr(node,'body') and isinstance(node.body,list) and not node.body and not isinstance(node,ast.Module):
            node.body=[ast.Pass()]
    if known_functions:
        class ExactReviewedFunctions(ast.NodeTransformer):
            def visit_FunctionDef(self,node):
                digest=hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()
                prior=known_functions.get(digest)
                if prior:
                    return ast.Expr(value=ast.Constant(value=f'EXACT_REVIEWED_FUNCTION {node.name} sha256={digest} source={prior}'))
                return self.generic_visit(node)
        tree=ExactReviewedFunctions().visit(tree)
    return ast.unparse(ast.fix_missing_locations(tree))

def reviewed_functions():
    """Exact complete AST matches only; changed code is always displayed."""
    result={}
    for path,note in notes().items():
        p=ROOT/path
        if note['sha256']!=hashlib.sha256(p.read_bytes()).hexdigest():raise ValueError(path)
        rendered=core(p)
        if rendered.startswith('PARSE_FAILED'):continue
        for node in ast.walk(ast.parse(rendered)):
            if isinstance(node,ast.FunctionDef):
                digest=hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()
                result.setdefault(digest,path)
    return result

def notes():return json.loads(NOTES.read_text()) if NOTES.exists() else {}

def add_authored(entries,group='2020年度精选策略'):
    """Persist supplied, individually authored notes; never infer decisions."""
    reviewed=notes()
    for prefix,fields in entries.items():
        matches=[p for p in (ROOT/'quant'/group).glob(prefix+'*') if p.suffix.lower() in {'.txt','.py','.ipynb'}]
        if len(matches)!=1:raise ValueError((prefix,matches))
        p=matches[0];logic,formula,data,status,warnings=fields
        reviewed[str(p.relative_to(ROOT))]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
            'logic':logic,'factor_recipes':formula,'data_requirements':data,'status':status,'warnings':warnings,
            'review_basis':'complete rendered source read; exact previously reviewed function matches may be referenced; active calls and changed parameters checked'}
    NOTES.write_text(json.dumps(reviewed,ensure_ascii=False,indent=2)+'\n')
    refresh()

def refresh():
    reviewed=notes();ledger=pd.read_csv(DEST/'source_review.csv').fillna('')
    tested={}
    extra=[]
    cohorts=[]
    supplements=list((ROOT/'research_reports/platform_alignment').glob('quant-corpus-semantic-*/recipe_manifest.json'))
    supplements+=list((ROOT/'research_reports/platform_alignment').glob('quant-corpus-nested-local-*/recipe_manifest.json'))
    for supplement in sorted(supplements):
        completion=supplement.parent/'completion.json'
        if not completion.exists():continue
        done=json.loads(completion.read_text())
        if not (done.get('completed') or done.get('all_candidates_completed')):continue
        recipes=json.loads(supplement.read_text())
        extra.extend(recipes)
        cohorts.append({'directory':str(supplement.parent.relative_to(ROOT)),'specifications':len(recipes)})
    for m in extra:
        for p in m['source_paths']:tested.setdefault(p,[]).append(m['key'])
    for i,row in ledger.iterrows():
        n=reviewed.get(row.path)
        if n is None:continue
        assert n['sha256']==hashlib.sha256((ROOT/row.path).read_bytes()).hexdigest(),row.path
        ledger.loc[i,'review_level']='core_logic_and_formula_checked'
        warning_text=n.get('warnings','')
        if isinstance(warning_text,list):
            warning_text='；'.join(str(x) for x in warning_text)
        ledger.loc[i,'finding']=n['logic']+' | '+warning_text
        ledger.loc[i,'semantic_status']=n['status']
        ledger.loc[i,'source_factor_formulas']=n['factor_recipes']
        ledger.loc[i,'semantic_data_requirements']=n['data_requirements']
        ledger.loc[i,'review_basis']=n['review_basis']
        ledger.loc[i,'supplemental_tested_recipes']=';'.join(tested.get(row.path,[]))
    ledger.to_csv(DEST/'source_review.csv',index=False,encoding='utf-8-sig')
    coverage=json.loads((DEST/'review_coverage.json').read_text())
    coverage['review_levels']=ledger.review_level.value_counts().to_dict()
    coverage['individually_authored_semantic_reviews']=len(reviewed)
    coverage['remaining_texts_without_detailed_review']=int(ledger.review_level.eq('per_file_evidence_and_dependencies_reviewed').sum())
    coverage['all_readable_strategies_semantically_reviewed']=coverage['remaining_texts_without_detailed_review']==0
    coverage['supplemental_recipe_count']=len(extra)
    coverage['completed_supplemental_cohorts']=cohorts
    coverage['tested_specifications_total']=coverage['tested_recipe_count']+len(extra)
    (DEST/'review_coverage.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2)+'\n')
    ledger.to_json(DEST/'source_review.json',orient='records',force_ascii=False,indent=2)
    pd.DataFrame([{'path':p,**r} for p,r in reviewed.items()]).to_csv(DEST/'semantic_reviews.csv',index=False,encoding='utf-8-sig')
    checked=int(ledger.review_level.isin(['formula_and_code_checked','core_logic_and_formula_checked']).sum())
    status=DEST/'TASK_STATUS.md'
    if status.exists():
        body=status.read_text()
        body=re.sub(r'\| 详细公式/代码核对 \|[^\n]*',
            f'| 详细公式/代码核对 | {checked}个来源；其余{coverage["remaining_texts_without_detailed_review"]}个尚未完成逐篇详细核验 |',body)
        body=re.sub(r'\| 首轮92规格[^\n]*',
            f'| 本地已完成规格 | 首轮{coverage["tested_recipe_count"]}项，补读新增{len(extra)}项，共{coverage["tested_specifications_total"]}项；各批次五年/近期独立保存，不能混合规则排名 |',body)
        status.write_text(body)
    (DEST/'semantic_review_details.md').write_text('# 逐篇源码补读记录\n\n'
        '仅收录已逐篇核对并手写结论的来源；源码渲染和字段扫描不会自动提高阅读层级。\n\n'+
        '\n\n'.join(f'## {p}\n\n实际逻辑：{n["logic"]}\n\n可提取公式：{n["factor_recipes"]}\n\n数据条件：{n["data_requirements"]}\n\n处理状态：{n["status"]}\n\n实现注意：{n["warnings"]}\n\n源码 SHA256：`{n["sha256"]}`' for p,n in reviewed.items())+'\n')
    print(json.dumps(coverage,ensure_ascii=False,indent=2))

def main():
    p=argparse.ArgumentParser();p.add_argument('--group',default='2020年度精选策略');p.add_argument('--start',type=int,default=0);p.add_argument('--count',type=int,default=5);p.add_argument('--refresh',action='store_true');p.add_argument('--dedup-reviewed',action='store_true');a=p.parse_args()
    if a.refresh:refresh();return
    d=pd.read_csv(DEST/'source_review.csv');d=d[d.path.str.contains('/'+a.group+'/') & d.review_level.eq('per_file_evidence_and_dependencies_reviewed')]
    selected=d.iloc[a.start:a.start+a.count]
    known=reviewed_functions() if a.dedup_reviewed else None
    for _,r in selected.iterrows():
        rendered=core(ROOT/r.path,known)
        if known:
            # Retain every equivalence proof, but summarize repetitive links
            # in the terminal. No unreviewed function is removed.
            folder=DEST/'rendered_cores';folder.mkdir(exist_ok=True)
            target=folder/(hashlib.sha256(r.path.encode()).hexdigest()[:16]+'.txt')
            target.write_text(r.path+'\n'+rendered+'\n')
            lines=rendered.splitlines();refs=[x for x in lines if x.startswith("'EXACT_REVIEWED_FUNCTION ")]
            rendered=f'{len(refs)} exact previously reviewed functions; proofs: {target.relative_to(ROOT)}\n'+ '\n'.join(x for x in lines if x not in refs)
        print('\nSOURCE '+r.path+'\n'+rendered)

if __name__=='__main__':main()
