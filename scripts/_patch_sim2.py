from pathlib import Path
p = Path(r"D:/factor/scripts/turnover_relaxed_pool_sim_20260926.py")
t = p.read_text(encoding="utf-8")

old_daily = t[t.index("        def daily_curve(tag: str) -> pd.Series:"):t.index("        curves = {tag: daily_curve(tag) for tag in (\"seed\", \"six\")}")]
new_daily = '''        close_values = close.to_numpy(dtype="float64")

        def build_daily(tag: str) -> pd.DataFrame:
            """Official C ledger: buy-and-hold long basket vs buy-and-hold universe.

            Returns daily PORTFOLIO (cost-adjusted) and BENCHMARK returns; SR and
            MaxDD use the portfolio curve, Rex compounds the two separately.
            """
            lookup = {row["period"]: row for row in curated if row["scenario"] == tag}
            days, portfolio, benchmark = [], [], []
            for period, row in lookup.items():
                if not row["valid"]:
                    continue
                base = calendar_position[dates[period]] + 1
                if base + CYCLE >= len(cal):
                    continue
                rows = list(range(base, base + CYCLE + 1))
                block = close_values[rows]
                anchor = block[0]
                held = np.array([column_position[x] for x in row["instruments"]
                                 if x in column_position], dtype=np.int64)
                held = held[np.isfinite(anchor[held]) & (anchor[held] > 0)]
                if held.size < 10:
                    continue
                universe = np.flatnonzero(np.isfinite(anchor) & (anchor > 0))
                portfolio_value = np.nanmean(block[:, held] / anchor[held], axis=1)
                benchmark_value = np.nanmean(block[:, universe] / anchor[universe], axis=1)
                portfolio_return = portfolio_value[1:] / portfolio_value[:-1] - 1.0
                benchmark_return = benchmark_value[1:] / benchmark_value[:-1] - 1.0
                if np.isfinite(row["turnover"]):
                    portfolio_return[0] -= row["turnover"] * COST
                days.extend(cal[base + 1: base + CYCLE + 1])
                portfolio.extend(portfolio_return.tolist())
                benchmark.extend(benchmark_return.tolist())
            return pd.DataFrame({"portfolio": portfolio, "benchmark": benchmark},
                                index=pd.DatetimeIndex(days))

'''
t = t.replace(old_daily, new_daily)
t = t.replace('curves = {tag: daily_curve(tag) for tag in ("seed", "six")}',
              'curves = {tag: build_daily(tag) for tag in ("seed", "six")}')

old_month = t[t.index("        def monthly_table(tag: str) -> pd.DataFrame:"):t.index("        months = {tag: monthly_table(tag) for tag in (\"seed\", \"six\")}")]
new_month = '''        def monthly_table(tag: str) -> pd.DataFrame:
            """Official monthly C ledger (see competition_rules.md C section)."""
            frame = curves[tag]
            rows = []
            for (year, month), block in frame.groupby([frame.index.year, frame.index.month]):
                p = block["portfolio"].to_numpy(dtype="float64")
                b = block["benchmark"].to_numpy(dtype="float64")
                ok = np.isfinite(p) & np.isfinite(b)
                p, b = p[ok], b[ok]
                n = len(p)
                if n < 2:
                    continue
                r_p = float(np.prod(1 + p) - 1.0)
                r_b = float(np.prod(1 + b) - 1.0)
                rex_ann = (1 + r_p) ** (252.0 / n) - 1.0 - ((1 + r_b) ** (252.0 / n) - 1.0)
                std = float(p.std(ddof=1))
                sr_ann = float(p.mean() / std * np.sqrt(252.0)) if std > 0 else 0.0
                equity = np.cumprod(1 + p)
                dd = float(-(equity / np.maximum.accumulate(equity) - 1).min())
                mask = (ledger.date.dt.year == year) & (ledger.date.dt.month == month) \\
                       & (ledger.scenario == tag) & ledger.valid
                turns = ledger.turnover[mask].to_numpy(dtype="float64")
                turns = turns[np.isfinite(turns)]
                rows.append(dict(year=year, month=month, days=n, r_p=r_p, r_b=r_b,
                                 rex_ann=rex_ann, sr_ann=sr_ann, max_dd=dd,
                                 turnover_month=float(turns.sum())))
            return pd.DataFrame(rows)

'''
t = t.replace(old_month, new_month)
t = t.replace('curves[tag].rename("daily_excess").to_frame().to_csv(\n                OUT / f"daily_{name}_{tag}.csv", encoding="utf-8-sig")',
              'curves[tag].to_csv(OUT / f"daily_{name}_{tag}.csv", encoding="utf-8-sig")')
p.write_text(t, encoding="utf-8")
import ast
ast.parse(t)
print("patched v2 ok")