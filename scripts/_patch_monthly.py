import pathlib

p = pathlib.Path(r"D:\factor\scripts\ab_batch_20260925.py")
t = p.read_text(encoding="utf-8")

start = t.index('def monthly_dcomb(base_df, cand_df):')
end = t.index('def main() -> int:')
new = '''def _block_nc(group: pd.DataFrame) -> float:
    """一个分块内独立算 Rex/SR/DD/换手，再折算成 NC。"""
    held = group["held"].to_numpy()
    turn = group["turnover"].to_numpy()
    rex = float(np.prod(1 + held) ** (252.0 / CYCLE / len(group)) - 1)
    after = held - np.where(np.isfinite(turn), turn * COST, 0.0)
    sr = float(after.mean() / after.std(ddof=1) * np.sqrt(252.0 / CYCLE)) if after.std(ddof=1) else 0.0
    curve = np.cumprod(1 + after)
    dd = float(-(curve / np.maximum.accumulate(curve) - 1).min())
    threshold = float(np.nanmean(turn)) * 2
    return min(max(max(rex, 0.0) / max(threshold, 0.30) * sr * (1 - 1.2 * dd) / 0.6, 0.0), 1.0)


def monthly_dcomb(base_df, cand_df, block=None, min_periods=2):
    """分块日频账本口径的 ΔComb：每块独立算 Rex/SR/DD/换手 -> ΔNC -> ΔComb = 0.45*ΔNC。

    block=None 用自然月（10 日调仓下每月约 2 期）；block=N 用连续 N 期分块（更稳）。
    """
    def grouped(frame):
        data = frame[frame["valid"]].copy()
        if block:
            data["_key"] = (np.arange(len(data)) // int(block)).astype(str)
        else:
            data["_key"] = data["date"].dt.to_period("M").astype(str)
        return {str(k): g for k, g in data.groupby("_key")}

    base_groups, cand_groups = grouped(base_df), grouped(cand_df)
    out = []
    for key in sorted(set(base_groups) & set(cand_groups)):
        left, right = base_groups[key], cand_groups[key]
        if len(left) < min_periods or len(right) < min_periods:
            continue
        out.append(0.45 * (_block_nc(right) - _block_nc(left)))
    return out


'''
t = t[:start] + new + t[end:]

old = '''        md = monthly_dcomb(base_df, df6)
        monthly.append(dict(candidate=name, n_months=len(md),
                            dcomb_month_mean=float(np.mean(md)) if md else np.nan,
                            dcomb_month_positive=float(np.mean([x > 0 for x in md])) if md else np.nan,
                            dcomb_points_month_mean=POINTS * float(np.mean(md)) if md else np.nan))
'''
new_call = '''        md = monthly_dcomb(base_df, df6)
        blk = monthly_dcomb(base_df, df6, block=6)
        monthly.append(dict(candidate=name, n_months=len(md),
                            dcomb_month_mean=float(np.mean(md)) if md else np.nan,
                            dcomb_month_positive=float(np.mean([x > 0 for x in md])) if md else np.nan,
                            dcomb_points_month_mean=POINTS * float(np.mean(md)) if md else np.nan,
                            n_blocks=len(blk),
                            dcomb_block6_mean=float(np.mean(blk)) if blk else np.nan,
                            dcomb_block6_positive=float(np.mean([x > 0 for x in blk])) if blk else np.nan))
'''
assert old in t
t = t.replace(old, new_call, 1)
p.write_text(t, encoding="utf-8")
import ast
ast.parse(t)
print("patched ok")