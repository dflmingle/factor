# D02/D03 字段与协方差诊断

规则版本：`full-a-qfq-label1-financialfix2-tieproxy1-pythonindex1-turnoverdiag1`

仅使用本地 Tushare 缓存和已保存 PandaAI 结果；没有创建因子或发起回测。

| family | candidate | finite | periods | local RankIC | local gross | platform gross | gross delta pp | local net | platform net | net delta pp | local net @ platform cost | residual pp | Top20 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| D02 | `D02-comm_exp-cache-keep_missing_reports` | 9361 | 58 | -0.0048 | -11.2238% | 2.5900% | -13.8138 | -12.0935% | -24.7318% | 12.6384 | -38.5457% | -13.8138 | 1/20 |
| D02 | `D02-comm_exp-cache-exclude_missing_reports` | 8258 | 58 | 0.0110 | -6.8530% | 2.5900% | -9.4430 | -7.5361% | -24.7318% | 17.1958 | -34.1749% | -9.4430 | 1/20 |
| D02 | `D02-comm_exp-end_date_latest-keep_missing_reports` | 9357 | 58 | -0.0047 | -11.0971% | 2.5900% | -13.6871 | -11.9355% | -24.7318% | 12.7963 | -38.4189% | -13.6871 | 1/20 |
| D02 | `D02-comm_exp-end_date_latest-exclude_missing_reports` | 8258 | 58 | 0.0111 | -6.8586% | 2.5900% | -9.4486 | -7.4659% | -24.7318% | 17.2659 | -34.1805% | -9.4486 | 1/20 |
| D02 | `D02-comm_exp-field_store-field_store_nonempty_reports` | 7929 | 58 | 0.0114 | -5.9447% | 2.5900% | -8.5347 | -6.4326% | -24.7318% | 18.2992 | -33.2665% | -8.5347 | 1/20 |
| D02 | `D02-insurance_exp-cache-keep_missing_reports` | 0 | 0 | n/a | n/a% | 2.5900% | n/a | n/a% | -24.7318% | n/a | n/a% | n/a | 0/20 |
| D02 | `D02-insurance_exp-cache-exclude_missing_reports` | 0 | 0 | n/a | n/a% | 2.5900% | n/a | n/a% | -24.7318% | n/a | n/a% | n/a | 0/20 |
| D02 | `D02-insurance_exp-end_date_latest-keep_missing_reports` | 0 | 0 | n/a | n/a% | 2.5900% | n/a | n/a% | -24.7318% | n/a | n/a% | n/a | 0/20 |
| D02 | `D02-insurance_exp-end_date_latest-exclude_missing_reports` | 0 | 0 | n/a | n/a% | 2.5900% | n/a | n/a% | -24.7318% | n/a | n/a% | n/a | 0/20 |
| D02 | `D02-insurance_exp-field_store-field_store_nonempty_reports` | 0 | 0 | n/a | n/a% | 2.5900% | n/a | n/a% | -24.7318% | n/a | n/a% | n/a | 0/20 |
| D03 | `D03-cache-keep_missing_reports-centered-ddof1-float64-scale1` | 6955 | 15 | -0.0187 | -19.5577% | 7.7600% | -27.3177 | -20.3677% | -12.9151% | -7.4526 | -40.2328% | -27.3177 | 3/20 |
| D03 | `D03-cache-keep_missing_reports-centered-ddof1-float32-scale1` | 6955 | 15 | 0.0284 | 10.8328% | 7.7600% | 3.0728 | 9.9418% | -12.9151% | 22.8569 | -9.8423% | 3.0728 | 3/20 |
| D03 | `D03-cache-keep_missing_reports-centered-ddof1-float64-scale1e+08` | 6955 | 15 | -0.0124 | -10.3990% | 7.7600% | -18.1590 | -11.3890% | -12.9151% | 1.5261 | -31.0741% | -18.1590 | 3/20 |
| D03 | `D03-cache-keep_missing_reports-moment-ddof0-float64-scale1` | 6955 | 15 | 0.0060 | 4.1466% | 7.7600% | -3.6134 | 2.9242% | -12.9151% | 15.8393 | -16.5285% | -3.6134 | 3/20 |
| D03 | `D03-cache-exclude_missing_reports-centered-ddof1-float64-scale1` | 14999 | 122 | -0.0014 | -1.5516% | 7.7600% | -9.3116 | -6.4847% | -12.9151% | 6.4304 | -22.2267% | -9.3116 | 6/20 |
| D03 | `D03-cache-exclude_missing_reports-centered-ddof1-float32-scale1` | 14999 | 122 | 0.0011 | 3.1948% | 7.7600% | -4.5652 | -0.8125% | -12.9151% | 12.1026 | -17.4803% | -4.5652 | 4/20 |
| D03 | `D03-cache-exclude_missing_reports-centered-ddof1-float64-scale1e+08` | 14999 | 122 | 0.0019 | 8.0097% | 7.7600% | 0.2497 | 3.7363% | -12.9151% | 16.6514 | -12.6654% | 0.2497 | 3/20 |
| D03 | `D03-cache-exclude_missing_reports-moment-ddof0-float64-scale1` | 14999 | 122 | 0.0189 | 6.9129% | 7.7600% | -0.8471 | 2.4481% | -12.9151% | 15.3631 | -13.7622% | -0.8471 | 3/20 |
| D03 | `D03-end_date_latest-keep_missing_reports-centered-ddof1-float64-scale1` | 6957 | 15 | -0.0187 | -19.5577% | 7.7600% | -27.3177 | -20.3677% | -12.9151% | -7.4526 | -40.2328% | -27.3177 | 3/20 |
| D03 | `D03-end_date_latest-keep_missing_reports-centered-ddof1-float32-scale1` | 6957 | 15 | 0.0284 | 10.8328% | 7.7600% | 3.0728 | 9.9418% | -12.9151% | 22.8569 | -9.8423% | 3.0728 | 3/20 |
| D03 | `D03-end_date_latest-keep_missing_reports-centered-ddof1-float64-scale1e+08` | 6957 | 15 | -0.0124 | -10.3990% | 7.7600% | -18.1590 | -11.3890% | -12.9151% | 1.5261 | -31.0741% | -18.1590 | 3/20 |
| D03 | `D03-end_date_latest-keep_missing_reports-moment-ddof0-float64-scale1` | 6957 | 15 | 0.0060 | 4.1466% | 7.7600% | -3.6134 | 2.9242% | -12.9151% | 15.8393 | -16.5285% | -3.6134 | 3/20 |
| D03 | `D03-end_date_latest-exclude_missing_reports-centered-ddof1-float64-scale1` | 14999 | 122 | -0.0014 | -1.5516% | 7.7600% | -9.3116 | -6.4847% | -12.9151% | 6.4304 | -22.2267% | -9.3116 | 6/20 |
| D03 | `D03-end_date_latest-exclude_missing_reports-centered-ddof1-float32-scale1` | 14999 | 122 | 0.0011 | 3.1948% | 7.7600% | -4.5652 | -0.8125% | -12.9151% | 12.1026 | -17.4803% | -4.5652 | 4/20 |
| D03 | `D03-end_date_latest-exclude_missing_reports-centered-ddof1-float64-scale1e+08` | 14999 | 122 | 0.0019 | 8.0097% | 7.7600% | 0.2497 | 3.7363% | -12.9151% | 16.6514 | -12.6654% | 0.2497 | 3/20 |
| D03 | `D03-end_date_latest-exclude_missing_reports-moment-ddof0-float64-scale1` | 14999 | 122 | 0.0189 | 6.9129% | 7.7600% | -0.8471 | 2.4481% | -12.9151% | 15.3631 | -13.7622% | -0.8471 | 3/20 |
| D03 | `D03-field_store-field_store_nonempty_reports-centered-ddof1-float64-scale1` | 13319 | 89 | 0.0052 | -0.1200% | 7.7600% | -7.8800 | -4.1241% | -12.9151% | 8.7910 | -20.7951% | -7.8800 | 6/20 |
| D03 | `D03-field_store-field_store_nonempty_reports-centered-ddof1-float32-scale1` | 13319 | 89 | 0.0153 | 6.9250% | 7.7600% | -0.8350 | 3.4312% | -12.9151% | 16.3463 | -13.7501% | -0.8350 | 4/20 |
| D03 | `D03-field_store-field_store_nonempty_reports-centered-ddof1-float64-scale1e+08` | 13319 | 89 | -0.0024 | 5.2381% | 7.7600% | -2.5219 | 0.8337% | -12.9151% | 13.7488 | -15.4370% | -2.5219 | 3/20 |
| D03 | `D03-field_store-field_store_nonempty_reports-moment-ddof0-float64-scale1` | 13319 | 89 | 0.0136 | 8.0623% | 7.7600% | 0.3023 | 4.0480% | -12.9151% | 16.9631 | -12.6128% | 0.3023 | 3/20 |

## 当前结论

- D03 严格按 `_report_panel()` 的非空报告序号、中心化 `ddof=1`、`float32` 诊断为 89 个有效期；本地毛超额约 `6.93%`，平台为 `7.76%`。把平台年化成本 `20.6751%` 套到本地毛超额后约为 `-13.75%`，与平台净超额 `-12.9151%` 只差约 `-0.8350pp`，说明净超额差主要来自换手摘要口径，但字段值/有效期和 Top20（4/20）仍未完全复现。
- D02 的 `comm_exp` 最接近的严格报告语义仍比平台毛超额低约 `8.53pp`，套用平台成本后与平台净超额仍差约 `-8.53pp`；`insurance_exp` 当前无可用记录。因此 D02 不能靠换手成本口径抹平。

## 解释边界

- D02 的 `insurance_exp` 与 `comm_exp` 都是 Tushare 候选代理；结果不能证明任一字段等价于平台字段。
- D03 的 `proc_issue_bonds` 是 `cash_received_from_issuing_security` 的 Tushare 字段代理；中心化 `ddof=1` 才对应 AlphaPROBE `TsCov` 的已知实现。
- 金额缩放只改变协方差数值尺度，若不改变浮点排序，通常不会改变分组；`float32`/矩估计的结果用于识别数值抵消。
- `platform_gross_excess_pct` 来自保存结果的分组毛超额；`platform_net_excess_pct` 和平台成本来自同一批次 CSV。净超额差必须与平台净超额比较，不能把本地净超额减平台毛超额。
- `local_net_using_platform_cost_pct` 是本地毛超额减去平台批次的年化成本，仅用于拆分换手影响；它不是正式本地净超额。若该值已接近平台净超额，差异主要由平台/本地换手摘要口径造成。
- 正式规则未因本诊断改变；任何采用新代理的正式复现都必须递增规则版本并使用新目录。
