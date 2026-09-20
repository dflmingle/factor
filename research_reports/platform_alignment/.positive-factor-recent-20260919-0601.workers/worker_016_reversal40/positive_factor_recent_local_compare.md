# Recent local diagnostics for platform-net-positive factors

Machine: `home` (家用电脑).
This report is a recent-window diagnostic, not a replacement for the canonical five-year alignment report.
Alignment rules: `full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1-qualitygate1`; see `research_reports/platform_alignment/ALIGNMENT_RULES.md`.
Factor values use `2018-01-01 00:00:00` warm-up; portfolio statistics use signal dates from `2026-06-01 00:00:00`.
The platform net column is the saved full-window screening result. It is not a recent-window platform return.

- positive platform records: `2`
- locally reproduced: `2`
- no local handler or no usable recent dates: `0`
- recent signal dates: `2026-06-05 00:00:00` to `2026-08-24 00:00:00`

## Recent results

Net, gross and cost values are arithmetic annualized percentages over the recent signal dates.

| name | handler | cycle | recent periods | platform net full window | recent local net | recent gross | annual cost | turnover | RankIC |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| OSR2-RET40 | reversal40 | 10 | 5 | 5.03% | 27.16% | 35.29% | 8.13% | 53.76% | 0.1688 |
| OSR2-RET40 | reversal40 | 5 | 12 | 1.03% | 5.77% | 17.58% | 11.81% | 39.06% | 0.0711 |

## Not locally reproduced

| name | handler | cycle | platform net full window | reason |
|---|---|---:|---:|---|

## Interpretation limits

- The recent window is short and regime-sensitive; it is not a standalone factor acceptance test.
- Local values follow the canonical qfq/full-A/total_mv/label-1 contract. Proxy and alignment status remain attached to the original five-year catalog.
- A positive recent local net excess does not override a large five-year local/platform mismatch.
