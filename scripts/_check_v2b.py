import io, sys
import numpy as np, pandas as pd
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
pd.set_option("display.width", 220)
base = r"D:/factor/research_reports/platform_alignment/turnover-relaxed-20260926"
rows = []
for tag in ("T1_ratio_bm_vma250", "T2_tsmed_amount", "T4_ev_lyr", "T5_totliab"):
    d = pd.read_csv(f"{base}/monthly_{tag}.csv")
    for basis in ("local", "uplifted"):
        s = d[(d.basis == basis) & (d.scenario == "seed")].sort_values(["year", "month"]).reset_index(drop=True)
        x = d[(d.basis == basis) & (d.scenario == "six")].sort_values(["year", "month"]).reset_index(drop=True)
        dp = x.points - s.points
        m = s.merge(x, on=["year", "month"], suffixes=("_s", "_x"))
        m["dp"] = m.points_x - m.points_s
        yearly = m.groupby("year")["dp"].mean()
        na_term = (x.na.iloc[0] - s.na.iloc[0]) * 0.20 * 44000
        rows.append(dict(
            cand=tag, basis=basis,
            total=dp.mean(), na_term=na_term, c_term=dp.mean() - na_term,
            pos_months=int((dp > 0).sum()), neg_months=int((dp < 0).sum()),
            worst=dp.min(), best=dp.max(),
            y2022=yearly.get(2022, np.nan), y2023=yearly.get(2023, np.nan),
            y2024=yearly.get(2024, np.nan), y2025=yearly.get(2025, np.nan),
            y2026=yearly.get(2026, np.nan)))
t = pd.DataFrame(rows)
print(t.round(1).to_string(index=False))