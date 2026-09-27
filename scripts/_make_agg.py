from pathlib import Path
import ast
src = Path(r"D:/factor/scripts/turnover_relaxed_pool_sim_20260926.py").read_text(encoding="utf-8")

src = src.replace(
 'CANDIDATES = {\n "T1_ratio_bm_vma250"',
 'CATALOG = (ROOT / "quantlab/.quantlab/cache/research/cn_equity/reports/"\n'
 '           "all_factor_compare_full_a_label1_financialfix2_tieproxy1_pythonindex1_"\n'
 '           "turnoverdiag1_qualitygate1/all_factor_local_compare.json")\n'
 'CANDIDATES_OLD = {\n "T1_ratio_bm_vma250"')
src = src.replace('def main() -> int:', 'CANDIDATES = {"AGG": ("t10_size_plus_impact_aggregate", 1, 0.044726578555797855)}\n\n\ndef main() -> int:')
src = src.replace('    names = [n for n in (args.only.split(",") if args.only else list(CANDIDATES)) if n]',
                  '    names = list(CANDIDATES)')
src = src.replace('    del frame\n    gc.collect()\n\n    namespace = gp.expression_namespace()',
                  '    namespace = gp.expression_namespace()\n'
                  '    financial = e.load_financial_cache(e.DEFAULT_FINANCIAL_ROOT)\n'
                  '    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))["results"]\n'
                  '    frame_mask = frame["date"].isin(dates)\n'
                  '    rebuilt = frame.loc[frame_mask, ["date", "instrument"]].reset_index(drop=True)\n'
                  '    assert rebuilt.equals(signal_frame), "signal frame mismatch"')

old = src[src.index('        formula = CANDIDATES[name]'):src.index('        blocks = e._build_blocks(signal_frame, score_frame, returns_table, dates, keys)')]
new = '''        handler, direction, seat_si = CANDIDATES[name]
        pool_rows = [r for r in catalog if r.get("handler") == handler
                     and int(r.get("cycle") or 0) == CYCLE and r.get("local_mining_eligible")]
        spec = max(pool_rows, key=lambda r: r.get("platform_net_excess_pct") or -99.0)
        values = e.build_factor(frame, handler, financial=financial, signal_dates=dates)
        series = pd.to_numeric(values.loc[frame_mask].reset_index(drop=True), errors="coerce")
        finite_share = float(np.isfinite(series.to_numpy()).mean())
        print(f"[{name}] handler={handler} name={spec.get('name')} "
              f"platform_net={spec.get('platform_net_excess_pct')} finite_share={finite_share:.4f}",
              flush=True)
        stats = {"s_i_rank": seat_si}
        cand_score = e._competition_cross_sectional_scores(
            signal_frame, {handler: series},
            [{"key": "cand", "handler": handler, "direction": direction}])
        score_frame = pd.concat([seats, cand_score], axis=1).loc[:, keys]

'''
src = src.replace(old, new)
Path(r"D:/factor/scripts/agg_validate_20260926.py").write_text(src, encoding="utf-8")
ast.parse(src)
print("agg_validate written")