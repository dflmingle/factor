# PandaAI Factor Research Report

- Candidates: 2; completed: 0; failed: 2
- Settings: 10-day rebalance, 10 groups, 0.30% one-way cost
- Multiple-testing reference: p < 0.0250
- `long_sharpe`, drawdown, and monthly win rate are direction-selected single-factor diagnostics, not official pool-level C metrics.
- Full CLI payloads are retained at the `raw_result` paths in the CSV.

| name | direction | rank_ic | ic_ir | long_excess_pct | turnover_pct | annual_cost_pct | net_excess_pct | long_sharpe | long_max_drawdown_pct | long_monthly_win_rate_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - | - | - | - | - |

## Failures

- `POOL6-BHV-ADD-20261003`: run: Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "C:\Users\58302\.local\bin\pandaai-cli.exe\__main__.py", line 10, in <module>
  File "C:\Users\58302\AppData\Roaming\uv\tools\pandaai-cli\Lib\site-packag
- `POOL5-BHV-SWAPF-20261003`: run: Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "C:\Users\58302\.local\bin\pandaai-cli.exe\__main__.py", line 10, in <module>
  File "C:\Users\58302\AppData\Roaming\uv\tools\pandaai-cli\Lib\site-packag
