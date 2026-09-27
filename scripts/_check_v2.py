import io, sys
import numpy as np, pandas as pd
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
pd.set_option("display.width", 220)
base = r"D:/factor/research_reports/platform_alignment/turnover-relaxed-20260926"
for tag in ("T2_tsmed_amount", "T4_ev_lyr", "T1_ratio_bm_vma250", "T5_totliab"):
    d = pd.read_csv(f"{base}/monthly_{tag}.csv")
    print("="*100)
    print(tag)
    for basis in ("local", "uplifted"):
        s = d[(d.basis == basis) & (d.scenario == "seed")].sort_values(["year", "month"])
        x = d[(d.basis == basis) & (d.scenario == "six")].sort_values(["year", "month"])
        m = s.merge(x, on=["year", "month", "basis"], suffixes=("_s", "_x"))
        na_term = (x.na.iloc[0] - s.na.iloc[0]) * 0.20 * 44000
        dc = (m.points_x - m.points_s).mean() - na_term
        print(f"  basis={basis:8s} seed T={s.turnover_month.mean():.3f} six T={x.turnover_month.mean():.3f} | "
              f"seed NC={s.nc.mean():.3f} ({int((s.nc>0.9999).sum())}/60 =1) six NC={x.nc.mean():.3f} "
              f"({int((x.nc>0.9999).sum())}/60 =1) | NA term={na_term:+.0f} C term={dc:+.0f} "
              f"total={(m.points_x-m.points_s).mean():+.0f}")
    s = d[(d.basis == "uplifted") & (d.scenario == "seed")].sort_values(["year", "month"])
    print("  seed monthly: NC=1 in", int((s.nc > 0.9999).sum()), "months; NC<0.9 in",
          int((s.nc < 0.9).sum()), "months; min NC %.3f" % s.nc.min())
    print("  seed first 6 months:")
    print(s[["year","month","days","r_p","r_b","rex_ann","sr_ann","max_dd","turnover_month","nc"]].head(6).round(4).to_string(index=False))