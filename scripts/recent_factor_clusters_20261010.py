"""Offline October candidate census and reproducible correlation clustering.

No platform calls and no return scoring. Rebuild historical references under the
current field rules; never mix the undocumented September numpy grid with them.
"""
from __future__ import annotations

import argparse
import ast
import gc
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PA = ROOT / "research_reports/platform_alignment"
OUT = PA / "recent-factor-clusters-20261010-average-rank-v2"
sys.path.insert(0, str(ROOT / "scripts"))


def normalize(s):
    return re.sub(r"\s+", "", re.sub(r"\bSTD\(", "STDDEV(", s)).lower()


def algebra_key(formula):
    """Exact arithmetic simplification, with operator calls as opaque atoms.

    Unlike a bag-of-rank-legs signature, this retains every coefficient and
    sign. Equal legs at different weights are never declared formula duplicates.
    """
    import sympy as sp
    aliases = {"std":"stddev", "tsstd":"stddev", "tsmean":"ma", "ref":"delay",
               "tspctchange":"returns", "tsmax":"ts_max", "tssum":"sum", "inv":"inv"}
    def visit(node):
        if isinstance(node, ast.Constant): return sp.Rational(str(node.value))
        if isinstance(node, ast.Name): return sp.Symbol(node.id.lower())
        if isinstance(node, ast.UnaryOp):
            return -visit(node.operand) if isinstance(node.op, ast.USub) else visit(node.operand)
        if isinstance(node, ast.BinOp):
            a,b = visit(node.left),visit(node.right)
            if isinstance(node.op, ast.Add): return a+b
            if isinstance(node.op, ast.Sub): return a-b
            if isinstance(node.op, ast.Mult): return a*b
            if isinstance(node.op, ast.Div): return a/b
            if isinstance(node.op, ast.Pow): return a**b
        if isinstance(node, ast.Call) and isinstance(node.func,ast.Name):
            name = aliases.get(node.func.id.lower(),node.func.id.lower())
            args = [str(sp.cancel(visit(a))) for a in node.args]
            if name == "inv" and len(args) == 1: return 1/visit(node.args[0])
            return sp.Symbol(name+"("+",".join(args)+")")
        raise ValueError("unsupported algebra node")
    try:
        return str(sp.cancel(visit(ast.parse(formula,mode="eval").body)))
    except Exception:
        return "text:"+normalize(formula)


def inventory():
    from caltech_legs_20261003 import LEG_FIELDS, COMPOSITES
    rows = []

    def add(name, formula, source, kind, reason=""):
        rows.append(dict(name=name, formula=formula, source=str(source), kind=kind,
                         exclusion_reason=reason))

    files = [p for p in sorted(PA.rglob("*.txt"))
             if re.search(r"2026100[1-9]", str(p)) and "candidate" in p.name]
    files += [ROOT / "sizecap_net_s911_20261009-candidates.txt"]
    for path in files:
        for line in path.read_text().splitlines():
            if line.strip().startswith("#") or "~" not in line:
                continue
            parts = line.split("~")
            if len(parts) != 3:
                continue
            name, formula, direction = [p.strip() for p in parts]
            reason = "Python/pool wrapper: requires archived runtime signal reconstruction" if formula.endswith(".py") else ""
            add(name, formula, path.relative_to(ROOT), "platform_candidate", reason)

    raw = {
        "intr20": "0-MA((CLOSE-OPEN)/OPEN,20)", "amt60": "0-MA(AMOUNT,60)",
        "retrev5": "0-RETURNS(CLOSE,5)", "retrev10": "0-RETURNS(CLOSE,10)",
        "retrev20": "0-RETURNS(CLOSE,20)", "vs_756": "0-STDDEV(VOLUME,6)/STDDEV(VOLUME,756)",
        "vs_500": "0-STDDEV(VOLUME,6)/STDDEV(VOLUME,500)",
        "amihud20": "0-MA(ABS(RETURNS(CLOSE,1))/AMOUNT,20)",
        "t_lvl": "0-TURNOVER", "t_ma5": "0-MA(TURNOVER,5)", "t_ma20": "0-MA(TURNOVER,20)",
        "t_std20": "0-STDDEV(TURNOVER,20)", "cstd20": "0-STDDEV(CLOSE,20)",
        "cstd20_60": "0-STDDEV(CLOSE,20)/STDDEV(CLOSE,60)",
        "drift20": "0-MA(CLOSE*VOLUME/(AMOUNT*10)-1,20)",
        "downup": "0-STDDEV(RETURNS(CLOSE,1)-ABS(RETURNS(CLOSE,1)),20)/STDDEV(RETURNS(CLOSE,1)+ABS(RETURNS(CLOSE,1)),20)",
        "near52w": "CLOSE/TS_MAX(HIGH,250)", "mom250_20": "DELAY(CLOSE,20)/DELAY(CLOSE,250)-1",
        "on20": "0-MA(OPEN/DELAY(CLOSE,1)-1,20)",
        "on_minus_id": "MA(OPEN/DELAY(CLOSE,1)-1,20)-MA(CLOSE/OPEN-1,20)",
        "cgo500": "CLOSE/(SUM(TURNOVER*AMOUNT*10/VOLUME,500)/SUM(TURNOVER,500))-1",
        "limitup20": "0-COUNT(RETURNS(CLOSE,1)>=0.095,20)",
        "illq_t20": "0-MA(ABS(RETURNS(CLOSE,1))/TURNOVER,20)",
        "vwt20": "SUM(VOLUME*RETURNS(CLOSE,1),20)/SUM(VOLUME,20)",
        "skew60": "0-TS_SKEW(RETURNS(CLOSE,1),60)",
    }
    for name, (field, direction) in LEG_FIELDS.items():
        raw[name] = f"({direction})*({field})"
    for name, legs in COMPOSITES.items():
        raw[name] = "(" + "+".join(f"RANK({raw[k]})" for k in legs) + f")/{len(legs)}"
    specs = [PA / "alphagen-pool-opt-20261002/specs_alphagen.json",
             PA / "behavioral-20261003/specs_behavioral_20261003.json",
             PA / "behavioral-20261003/specs_behavioral_round2.json",
             PA / "caltech-20261003/specs_caltech_20261003.json",
             PA / "caltech-swap-20261003/specs_caltech_swap_20261003.json"]
    specs += sorted((PA / "legmix-size-20261009").glob("*_specs.json"))
    for path in specs:
        obj = json.loads(path.read_text())
        records = obj if isinstance(obj, list) else [dict(name=obj["tag"]+f"-k{s['k']}", **s) for s in obj["steps"]]
        for spec in records:
            signed = spec.get("signed", {})
            absent = sorted(set(signed) - raw.keys())
            reason = "unmapped legs: " + ",".join(absent) if absent else ""
            if not signed:
                reason = "no static leg specification"
            # Swap changes the pool, not the signal of this candidate leg.
            if reason:
                formula = json.dumps(signed, sort_keys=True)
            else:
                # AlphaGen W entries use magnitudes as weights; other specs
                # explicitly use sign*raw before ranking and equal weighting.
                weighted = path.name == "specs_alphagen.json" and spec["name"].endswith("W")
                formula = "(" + "+".join(
                    (f"{abs(w)}*" if weighted else "") + f"RANK(({1 if w >= 0 else -1})*({raw[k]}))"
                    for k, w in signed.items()) + ")"
                formula += f"/{sum(abs(w) for w in signed.values()) if weighted else len(signed)}"
            add(spec["name"], formula, path.relative_to(ROOT), "local_saved_spec", reason)

    combo_path = PA / "alphagen-combination-20261009.json"
    for spec in json.loads(combo_path.read_text()).get("factor_specs", []):
        add(spec["name"], spec.get("formula", ""), combo_path.relative_to(ROOT), "local_component",
            "" if spec.get("formula") else "handler without static formula")
    add("alphagen-combination-dynamic-pools", "", combo_path.relative_to(ROOT), "dynamic_pool",
        "dynamic selector/weights, not a single static factor")

    gp_path = PA / "sizecap-gp-20261009/records_with_corr.csv"
    search = pd.read_csv(gp_path)
    selected = set()
    # Explicit deterministic shortlist: top ten in each published size cap.
    for cap in [.1, .2, .3, .4, .5, .7, 1.01]:
        selected.update(search[search.corr_size.abs() <= cap].nlargest(10, "net").index)
    for i, row in search.iterrows():
        add(f"GP-{i:04d}", row.formula, gp_path.relative_to(ROOT), "gp_search_record",
            "search population outside declared frontier shortlist" if i not in selected else "")
    frame = pd.DataFrame(rows)
    frame["candidate_id"] = ["O%04d" % i for i in range(len(frame))]
    frame["formula_key"] = frame.formula.map(normalize)
    active = frame[frame.exclusion_reason.eq("")].drop_duplicates("formula_key").copy()
    active["panel_id"] = ["cand_%04d" % i for i in range(len(active))]
    mapping = active.set_index("formula_key").panel_id.to_dict()
    frame["panel_id"] = frame.formula_key.map(mapping).fillna("")
    frame.to_csv(OUT / "inventory.csv", index=False)
    active.to_csv(OUT / "candidates.csv", index=False)

    old_dir = PA / "new-factor-cluster-20260930"
    import gp_candidates_vs_clusters_20260924 as M
    labels = M.parse_cluster_map(PA / "all-factor-cluster-expansion-20260919.clusters.csv")
    refs = pd.read_csv(old_dir / "members_evaluated.csv").rename(columns={"factor_a_name":"name", "factor_a_formula":"formula"})
    refs["cluster"] = refs.name.map(labels).fillna("unassigned")
    sep = pd.read_csv(old_dir / "new_factor_cluster_assignment.csv")
    sep = sep[sep.panel.eq("engine")].copy()
    sep["cluster"] = sep.assignment.str.replace("(旧簇)", "", regex=False).replace({"未入簇(孤立)":"SEP-isolated"})
    refs = pd.concat([refs, sep.rename(columns={"factor":"name"})[["name","formula","cluster"]]], ignore_index=True)
    refs["panel_id"] = ["member_%04d" % i for i in range(len(refs))]
    refs.to_csv(OUT / "references.csv", index=False)
    excluded = pd.read_csv(old_dir / "members_excluded.csv")
    proxy = pd.read_csv(old_dir / "new_factor_cluster_assignment.csv")
    proxy = proxy[~proxy.panel.eq("engine")].rename(columns={"factor":"name","assignment":"cluster","panel":"blocked"})
    pd.concat([excluded, proxy[["name","formula","cluster","blocked"]]], ignore_index=True).to_csv(OUT / "reference_exclusions.csv", index=False)
    # Include all remaining saved specs as census entries, without inventing
    # unimplemented field/handler equivalents.
    extra = []
    for path in sorted(PA.rglob("*specs*.json")):
        if not re.search(r"2026100[1-9]",str(path)) or path in specs: continue
        obj = json.loads(path.read_text())
        if not isinstance(obj,list): continue
        for spec in obj:
            signed = spec.get("signed",{})
            formula = json.dumps(signed,sort_keys=True)
            extra.append(dict(name=spec.get("name","unnamed"), formula=formula,
                source=str(path.relative_to(ROOT)),kind="additional_saved_spec",
                exclusion_reason="additional pool/handler specification: static signal not materialized",
                candidate_id=f"O{len(frame)+len(extra):04d}",formula_key=normalize(formula),panel_id=""))
    for filename in ["board-higha-20261008/local_screen.csv", "board-higha-20261008/local_repro_new/screen.csv"]:
        path = PA / filename
        for _, row in pd.read_csv(path).iterrows():
            extra.append(dict(name=row.candidate,formula="",source=str(path.relative_to(ROOT)),
                kind="board_local_construction",exclusion_reason="handler construction; original 20200601 warmup differs from current formal grid",
                candidate_id=f"O{len(frame)+len(extra):04d}",formula_key="",panel_id=""))
    if extra:
        frame = pd.concat([frame,pd.DataFrame(extra)],ignore_index=True)
        frame.to_csv(OUT / "inventory.csv",index=False)
    history = pd.read_csv(old_dir / "new_factor_cluster_assignment.csv").rename(columns={"factor":"name"})
    history = pd.concat([refs[["name","formula"]],history[["name","formula"]]],ignore_index=True).drop_duplicates(["name","formula"])
    seen = {}
    for _, row in history.iterrows(): seen.setdefault(algebra_key(row.formula), "historical:"+row['name'])
    duplicates = []
    for _,row in frame.iterrows():
        if row.exclusion_reason: continue
        key = algebra_key(row.formula)
        if key in seen:
            duplicates.append(dict(candidate_id=row.candidate_id,name=row['name'],duplicate_of=seen[key],formula=row.formula,method="exact arithmetic with opaque operator calls"))
        else: seen[key] = row.candidate_id+":"+row['name']
    pd.DataFrame(duplicates).to_csv(OUT / "formula_duplicates.csv",index=False)
    print(f"inventory={len(frame)} unique selected={len(active)} references={len(refs)} GP shortlist={len(selected)}", flush=True)


def expression_namespace():
    import torch
    import alphaprobe_gp_tushare as gp
    import gp_candidates_vs_clusters_20260924 as M
    from alphagen.data.expression import UnaryOperator
    ns = gp.expression_namespace()
    ns.update({"DELAY":ns["Ref"], "ZSCORE":M.CrossZScore, "IF":M.IfElse, "ZScore":M.CrossZScore})
    ns.update({"STD":ns["STDDEV"], "COUNT":ns["SUM"]})
    class AverageRank(UnaryOperator):
        def _apply(self, operand):
            valid = torch.isfinite(operand)
            return gp._average_rank_by_day(operand,valid) / valid.sum(dim=1,keepdim=True).clamp_min(1)
    ns.update({"Rank":AverageRank,"RANK":AverageRank})
    M.patch_expression_comparisons(); M.wrap_field_leaves(ns)
    # Native TsPctChange uses a window of n observations (thus n-1 lag).
    # Platform RETURNS explicitly means an n-trading-day lag, including n=1.
    ns["RETURNS"] = lambda expr,n: ns["Div"](ns["Sub"](expr,ns["Ref"](expr,n)),ns["Ref"](expr,n))
    return ns


def evaluate():
    import torch
    import alphaprobe_gp_tushare as gp
    import gp_candidates_vs_clusters_20260924 as M
    from platform_alignment_rules import ALIGNMENT_RULE_VERSION
    torch.set_num_threads(16)
    refs, candidates = [pd.read_csv(OUT / f) for f in ["references.csv", "candidates.csv"]]
    formula_map = dict(zip(pd.concat([refs,candidates]).panel_id,pd.concat([refs,candidates]).formula))
    formula_path = OUT / "panel_formulas.json"
    if formula_path.exists():
        assert json.loads(formula_path.read_text()) == formula_map, "panel formulas changed; use a new output directory"
    else:
        formula_path.write_text(json.dumps(formula_map,ensure_ascii=False,indent=2))
    meta_path = OUT / "metadata.json"
    dates = json.loads((PA / "new-factor-cluster-20260930/run_meta.json").read_text())["signal_dates"] if (PA / "new-factor-cluster-20260930/run_meta.json").exists() else json.loads((PA / "cluster-overlap-20260924/run_meta.json").read_text())["signal_dates"]
    frame = gp.load_full_a_data(gp.DEFAULT_BATCH_ROOT, gp.DEFAULT_CACHE_ROOT / "tushare_factor_recheck/daily_basic_full_a", pd.Timestamp("20180101"), pd.Timestamp("20260907"))
    frame = frame.astype({c:"float32" for c in frame.columns if frame[c].dtype == "float64"})
    stocks = sorted(frame.instrument.astype(str).unique())
    calendar = [d for d in gp.load_trade_dates(gp.DEFAULT_CACHE_ROOT) if pd.Timestamp("20180101") <= d <= pd.Timestamp("20260907")]
    meta = dict(rule_version=ALIGNMENT_RULE_VERSION, cluster_version="october-offline-clusters-average-rank-v2", threshold=.8,
                method="pairwise-complete daily cross-sectional Spearman mean", min_stocks=100,
                signal_dates=dates, stock_ids=stocks, warmup="20180101", end="20260907",
                comparison_grid="September fixed 120 signal dates (20210907..20260810)",
                reused_September_panels=False, platform_runs=0,
                inner_rank="average ties, zero-based pct as prior engine",
                platform_returns="CLOSE/DELAY(CLOSE,n)-1; GP-native TsPctChange retains saved engine semantics")
    if meta_path.exists():
        assert json.loads(meta_path.read_text()) == meta, "incompatible panel metadata"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    ns = expression_namespace()
    data = gp.TushareStockData.from_aligned_frame(frame=frame, calendar=calendar, instrument=stocks,
        start_time="20210907", end_time="20260907", max_backtrack_days=756,
        max_future_days=0, device=torch.device("cpu"), financial_root=gp.DEFAULT_FINANCIAL_ROOT)
    positions = {str(pd.Timestamp(d).date()):i for i,d in enumerate(data._evaluation_dates)}
    take = [positions[d] for d in dates]
    failures = []
    for _, row in pd.concat([refs, candidates]).iterrows():
        dest = OUT / "panels" / (row.panel_id+".npy")
        if dest.exists():
            continue
        try:
            expression = gp.evaluate_formula(row.formula, ns)
            with torch.no_grad():
                tensor = gp.finite_as_nan(expression.evaluate(data))
            values = tensor.detach().cpu().numpy()[take]
            ranks = M.rank_array(pd.DataFrame(values))
            if not (np.isfinite(ranks).sum(axis=1) >= 100).any():
                raise ValueError("no usable date with 100 valid stocks")
            np.save(dest, ranks)
            print(row.panel_id, row['name'], 'ok', flush=True)
            del tensor, values, ranks
        except Exception as exc:
            failures.append(dict(panel_id=row.panel_id, name=row['name'], formula=row.formula, error=str(exc)))
            print(row.panel_id, row['name'], 'FAILED', str(exc)[:180], flush=True)
        gc.collect()
    pd.DataFrame(failures, columns=["panel_id","name","formula","error"]).to_csv(OUT / "evaluation_failures.csv", index=False)


def correlate():
    from scipy.stats import rankdata
    refs, candidates = [pd.read_csv(OUT / f) for f in ["references.csv", "candidates.csv"]]
    all_rows = pd.concat([refs,candidates], ignore_index=True)
    valid = all_rows[all_rows.panel_id.map(lambda p:(OUT / "panels" / (p+".npy")).exists())].reset_index(drop=True)
    panels = [np.load(OUT / "panels" / (p+".npy")) for p in valid.panel_id]
    n = len(valid)
    sums = np.zeros((n,n)); counts = np.zeros((n,n), dtype=int)
    minimum = np.full((n,n), 10**9, dtype=int)
    for day in range(panels[0].shape[0]):
        # Group by missingness; ranks in equal masks remain exact Spearman.
        groups = {}
        for i,panel in enumerate(panels):
            mask = np.isfinite(panel[day])
            groups.setdefault(mask.tobytes(), []).append(i)
        gs = list(groups.values())
        for a, ii in enumerate(gs):
            for jj in gs[a:]:
                mask = np.isfinite(panels[ii[0]][day]) & np.isfinite(panels[jj[0]][day])
                nstocks = int(mask.sum())
                if nstocks < 100: continue
                x = rankdata(np.stack([panels[i][day,mask] for i in ii]), axis=1)
                y = rankdata(np.stack([panels[j][day,mask] for j in jj]), axis=1)
                x -= x.mean(axis=1,keepdims=True); y -= y.mean(axis=1,keepdims=True)
                denom = np.linalg.norm(x,axis=1)[:,None]*np.linalg.norm(y,axis=1)[None,:]
                with np.errstate(invalid="ignore",divide="ignore"):
                    rho = (x @ y.T)/denom
                ok = np.isfinite(rho)
                ix = np.ix_(ii,jj)
                sums[ix] += np.where(ok,rho,0); counts[ix] += ok
                minimum[ix] = np.minimum(minimum[ix],np.where(ok,nstocks,10**9))
                if ii != jj:
                    ix = np.ix_(jj,ii)
                    sums[ix] += np.where(ok.T,rho.T,0); counts[ix] += ok.T
                    minimum[ix] = np.minimum(minimum[ix],np.where(ok.T,nstocks,10**9))
        if day % 10 == 0: print(f"correlation date {day+1}/{panels[0].shape[0]} groups={len(gs)}",flush=True)
    with np.errstate(invalid="ignore",divide="ignore"):
        corr = sums/counts
    assert np.allclose(corr,corr.T,equal_nan=True)
    pd.DataFrame(corr,index=valid.panel_id,columns=valid.panel_id).to_csv(OUT / "correlation_matrix.csv")
    pd.DataFrame(counts,index=valid.panel_id,columns=valid.panel_id).to_csv(OUT / "valid_dates_matrix.csv")
    edges, parent = [], list(range(n))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for i in range(n):
        for j in range(i):
            if abs(corr[i,j]) >= .8:
                parent[find(i)] = find(j)
                edges.append(dict(a=valid.iloc[i]['name'],b=valid.iloc[j]['name'],a_panel=valid.iloc[i].panel_id,
                    b_panel=valid.iloc[j].panel_id,rho=corr[i,j],valid_dates=counts[i,j],min_stocks=minimum[i,j]))
    pd.DataFrame(edges).to_csv(OUT / "threshold_edges.csv",index=False)
    components = {}
    for i in range(n): components.setdefault(find(i),[]).append(i)
    labels, comp_rows = {}, []
    for number, indices in enumerate(components.values(),1):
        anchors = sorted(set(str(valid.iloc[i].cluster) for i in indices if pd.notna(valid.iloc[i].get('cluster'))))
        component = f"C{number:03d}"
        for i in indices: labels[i] = (component,";".join(anchors))
        comp_rows.append(dict(component=component,anchors=";".join(anchors),members=";".join(valid.iloc[i]['name'] for i in indices),
                             recent_count=sum(valid.iloc[i].panel_id.startswith("cand") for i in indices),bridge=len(anchors)>1))
    pd.DataFrame(comp_rows).to_csv(OUT / "components.csv",index=False)
    assignments = []
    for i,row in valid.iterrows():
        if not row.panel_id.startswith("cand"): continue
        old_indices = [j for j in range(n) if valid.iloc[j].panel_id.startswith("member") and np.isfinite(corr[i,j])]
        nearest = max(old_indices,key=lambda j:abs(corr[i,j])) if old_indices else None
        component, anchors = labels[i]
        assignments.append(dict(panel_id=row.panel_id,name=row['name'],formula=row.formula,component=component,
            anchors=anchors or "new/unanchored", nearest_reference=valid.iloc[nearest]['name'] if nearest is not None else "",
            nearest_cluster=valid.iloc[nearest].cluster if nearest is not None else "",rho=corr[i,nearest] if nearest is not None else np.nan,
            direct_anchor_matches=";".join(sorted(set(str(valid.iloc[j].cluster) for j in old_indices if abs(corr[i,j])>=.8)))))
    assignments = pd.DataFrame(assignments)
    assignments.to_csv(OUT / "assignments.csv",index=False)
    inv = pd.read_csv(OUT / "inventory.csv").fillna("")
    inv = inv.merge(assignments.drop(columns=["name","formula"]),on="panel_id",how="left")
    inv["status"] = np.where(inv.exclusion_reason.ne(""),"excluded",np.where(inv.component.notna(),"clustered","evaluation_failed"))
    inv.to_csv(OUT / "ledger.csv",index=False)
    assert len(inv) == len(pd.read_csv(OUT / "inventory.csv"))
    missing_refs = refs[~refs.panel_id.isin(valid.panel_id)]
    missing_refs.to_csv(OUT / "reference_evaluation_failures.csv",index=False)
    manifest = {}
    for file in sorted(OUT.glob("*.csv")):
        manifest[file.name] = hashlib.sha256(file.read_bytes()).hexdigest()
    for file in sorted((OUT / "panels").glob("*.npy")):
        manifest["panels/"+file.name] = hashlib.sha256(file.read_bytes()).hexdigest()
    (OUT / "sha256_manifest.json").write_text(json.dumps(manifest,indent=2))
    recent_components = pd.DataFrame(comp_rows)
    recent_components = recent_components[recent_components.recent_count > 0]
    unanchored = recent_components[recent_components.anchors.eq("")]
    duplicates = pd.read_csv(OUT / "formula_duplicates.csv")
    meta = json.loads((OUT / "metadata.json").read_text())
    excluded_refs = pd.read_csv(OUT / "reference_exclusions.csv")
    old_clusters = pd.read_csv(PA / "all-factor-cluster-expansion-20260919.clusters.csv")
    uncovered = sorted(set(old_clusters.cluster)-set(refs[refs.panel_id.isin(valid.panel_id)].cluster))
    status = inv.status.value_counts().to_dict()
    direct_count = int(assignments.direct_anchor_matches.ne("").sum())
    transitive_count = int(((assignments.anchors!="new/unanchored") & assignments.direct_anchor_matches.eq("")).sum())
    lines = ["# 10 月 1–9 日因子归簇与去重补录（2026-10-10）", "",
        f"共登记 **{len(inv)} 条研究记录**；选择 **{len(candidates)} 条文本去重后的静态公式**进行物化，成功 **{len(assignments)} 条**。"
        f"记录状态：已归簇 {status.get('clustered',0)}、物化失败 {status.get('evaluation_failed',0)}、排除/未计算 {status.get('excluded',0)}。", "",
        f"近期可用公式落入 **{len(recent_components)} 个连通分量**：带旧簇锚点 {len(recent_components)-len(unanchored)} 个；"
        f"无旧锚点 {len(unanchored)} 个（其中 {int((unanchored.recent_count == 1).sum())} 个单例）。无锚点不能认定为新 alpha。", "",
        f"按公式数计：{direct_count} 条直接匹配旧参考，{transitive_count} 条仅通过其他成员间接连入旧锚点，"
        f"{int(assignments.anchors.eq('new/unanchored').sum())} 条无旧锚点。直接匹配和间接连接在台账中分开保留。", "",
        f"符号化算术去重发现 **{len(duplicates)} 条同式别名**。`POOL6-CAND-C-20261009` 与历史 `LAMD10-K5V2` 同式，"
        "仅名称及等权表达不同，应作为历史因子的再测记录保留，不计作新因子。", "",
        "## 口径与完整性", "",
        f"规则版本 `{meta['rule_version']}`；全 A `.SH/.SZ`、qfq、total_mv、20180101 暖机。"
        "使用历史固定 120 个信号日（20210907..20260810）以延续旧分簇统计尺度。这是信号相关性整理，不计算收益、成本或近期收益诊断，也没有平台回测。", "",
        "所有配对均在每日共同有效股票上重新平均排名，再取日 Spearman 的算术均值；每天至少 100 只共同有效股票。"
        "绝对相关性 ≥0.80 连边并取连通分量；所以同一分量中的任意两成员不保证相关性均达 0.80。"
        "`Cxxx` 是本次计算的分量编号，不覆盖 B/N/S 历史编号；`anchors` 保留所有旧锚点，多锚点为桥接。", "",
        f"重建参考 {len(refs)} 条，成功 {len(refs)-len(missing_refs)} 条；另有 {len(excluded_refs)} 条旧字段缺失/代理记录单独排除。"
        "旧 .npy 面板未保存股票顺序元数据，本次未复用；参考因子在当前规则下重新计算，历史簇名仅作锚点。"
        "所有本地字段均为平台实现的代理，相关结果不能证明平台字节级等价。", "",
        f"历史 B/N 中未覆盖的 {len(uncovered)} 个簇：`{' / '.join(uncovered)}`。"
        "S03 的 Alpha191 参考代理与 VV6-1250 的不足预热代理未纳入正式矩阵；无旧锚点结论仅针对本次可用参考。", "",
        "GP 1,111 条搜索记录全量登记，物化范围固定为各已发布 size 相关性上限（.10/.20/.30/.40/.50/.70/1.01）净额前十的去重并集，共 32 条。"
        "其余搜索记录标记未计算。池级 Python 包装、动态选择器、未映射 handler 和旧暖机榜单构造也保留原因，未强行归簇。", "",
        "本地组合按保存的 signed/weight 配置重建；平台候选按原公式计算。不同权重不会被去重；"
        "VWAP 单位与缺失传播等差异可能使本地保存组合和平台公式成为不同代理，台账保留各自来源。", "",
        "修正本次适配器的两项差异：内部 `RANK` 使用平均并列秩；平台 `RETURNS(X,N)` 使用 N 日滞后。"
        "AlphaPROBE 原生 `TsPctChange` 保留已保存 GP 搜索时的 N 个观测窗口语义。原首轮被拒绝，见相邻目录 `recent-factor-clusters-20261010/REJECTED.md`。"
        "本次规则实现修复后的数值不与旧引擎统计混合，簇号只保留锚点映射。", "",
        "## 近期候选归属", "", "| 候选 | 最近参考 | 日均 rho | 直接达到门槛的旧簇 | 连通分量 |", "|---|---|---:|---|---|"]
    platform_ids = set(inv[inv.kind.eq('platform_candidate')].panel_id)
    shown = assignments[assignments.panel_id.isin(platform_ids)]
    for _, row in shown.iterrows():
        lines.append(f"| {row['name']} | {row.nearest_reference} | {row.rho:.4f} | {row.direct_anchor_matches or '—'} | {row.component} |")
    lines += ["", "## 本次分量", "", "| 分量 | 历史锚点 | 近期公式数 | 桥接 |", "|---|---|---:|---|"]
    for _, row in recent_components.iterrows():
        lines.append(f"| {row.component} | {row.anchors or '无（待验证）'} | {row.recent_count} | {'是' if row.bridge else '否'} |")
    lines += ["", "## 后续使用", "",
        "新候选先查同式台账，再查相关簇。旧簇内变体优先作为替换/混合实验记录，不按新独立来源计数；"
        "无锚点候选仍需独立验证净额、换手和池级边际。本次不据此变更因子池。", "",
        "## 产物与复跑", "",
        "- [完整台账](ledger.csv)：每条记录有来源、公式、状态与排除原因。",
        "- [静态公式归属](assignments.csv)、[连通分量](components.csv)、[阈值边](threshold_edges.csv)。",
        "- [同式重复](formula_duplicates.csv)、[物化失败](evaluation_failures.csv)、[旧参考排除](reference_exclusions.csv)。",
        "- [相关矩阵](correlation_matrix.csv)、[有效日期数矩阵](valid_dates_matrix.csv)、[日期与股票顺序](metadata.json)、[校验和](sha256_manifest.json)。",
        "- [独立数值校验](verification.json)、[重复信号校验](duplicate_signal_check.json)、[面板公式绑定](panel_formulas.json)。",
        "", "复跑：`python3 scripts/recent_factor_clusters_20261010.py inventory`，再执行 `evaluate` 和 `correlate`。"
        "已保存面板可断点复用；规则变化必须使用新目录。最后执行 `verify` 核对数值与台账。"
        "`.npy` 为可再生本地缓存，按仓库惯例不入 Git。", ""]
    (OUT / "summary.md").write_text("\n".join(lines),encoding="utf-8")
    print(inv.status.value_counts().to_dict(),flush=True)


def verify():
    """Independent checks on saved results, not another materialization run."""
    from scipy.stats import spearmanr
    matrix = pd.read_csv(OUT / "correlation_matrix.csv", index_col=0)
    count = pd.read_csv(OUT / "valid_dates_matrix.csv",index_col=0)
    inventory_frame = pd.read_csv(OUT / "inventory.csv")
    ledger = pd.read_csv(OUT / "ledger.csv")
    assert len(ledger) == len(inventory_frame) and ledger.candidate_id.is_unique
    assert set(ledger.status) <= {"clustered","excluded","evaluation_failed"}
    assert np.allclose(matrix,matrix.T,equal_nan=True)
    assert np.array_equal(count,count.T)
    edges = pd.read_csv(OUT / "threshold_edges.csv")
    assert edges.rho.abs().ge(.8).all() and edges.min_stocks.ge(100).all()
    refs,candidates = [pd.read_csv(OUT / f) for f in ["references.csv","candidates.csv"]]
    formula_map = dict(zip(pd.concat([refs,candidates]).panel_id,pd.concat([refs,candidates]).formula))
    formula_path = OUT / "panel_formulas.json"
    if formula_path.exists(): assert json.loads(formula_path.read_text()) == formula_map
    else: formula_path.write_text(json.dumps(formula_map,ensure_ascii=False,indent=2))
    checked = []
    ids = list(matrix.index)
    probes = [(ids[0],ids[-1]),(ids[1],ids[-2])]
    # Check both strong and lower correlations against scipy's independent
    # scalar Spearman routine; tie-heavy count signals get their own probe.
    probes += [(r.a_panel,r.b_panel) for _,r in edges.head(3).iterrows()]
    cand = pd.read_csv(OUT / "candidates.csv")
    tie = cand[cand.name.str.contains("LIMITUP|limitup",regex=True)]
    if len(tie): probes.append((tie.iloc[0].panel_id,ids[0]))
    for a,b in probes:
        left,right = [np.load(OUT / "panels" / (p+".npy")) for p in [a,b]]
        daily = []
        for x,y in zip(left,right):
            mask = np.isfinite(x)&np.isfinite(y)
            if mask.sum()<100 or np.std(x[mask])==0 or np.std(y[mask])==0: continue
            daily.append(float(spearmanr(x[mask],y[mask]).statistic))
        mean = float(np.mean(daily)) if daily else np.nan
        assert np.isclose(mean,matrix.loc[a,b],equal_nan=True,atol=1e-10)
        assert len(daily) == count.loc[a,b]
        checked.append(dict(a=a,b=b,rho=mean,valid_dates=len(daily)))
    checks = dict(inventory_reconciled=len(ledger),symmetry=True,threshold_edges=len(edges),
                  independent_spearman_checks=checked)
    (OUT / "verification.json").write_text(json.dumps(checks,indent=2))
    print(json.dumps(checks),flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["inventory","evaluate","correlate","verify"])
    args = parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True); (OUT / "panels").mkdir(exist_ok=True)
    globals()[args.stage]()


if __name__ == "__main__":
    main()
