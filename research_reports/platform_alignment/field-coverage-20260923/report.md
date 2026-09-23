# 平台字段覆盖盘点（2026-09-23）

- 公式模式基础字段（fields.md）：348 个
- 回测因子目录（14 张表）：909 个
- 本地可复现状态（AlphaPROBE field_coverage）：local_direct 354、local_proxy 779、local_derived 19

## 公式模式基础字段覆盖

| 口径 | 字段数 | 平台实测过 | 本地算过 | 完全没碰 |
| --- | ---: | ---: | ---: | ---: |
| fields.md 全部 | 348 | 40 | 303 | 43 |
| 回测目录 | 909 | 41 | 511 | 397 |

## 公式模式字段里完全没碰过的（按家族）

### 本地状态 `unavailable` — 38 个

| 字段 | 名称 |
| --- | --- |
| `accrued_staff_costs` | 长期应付职工薪酬 |
| `begin_period_cash_equivalent` | 期初现金及现金等价物余额 |
| `bill_receivable` | 应收票据 |
| `cash_flow_hedging_effective_portion` | 现金流量套期损益的有效部分 |
| `cash_paid_to_acquire_investment` | 投资支付的现金 |
| `cash_received_from_issuing_equity_instruments` | 发行其他权益工具收到的现金 |
| `cash_received_from_original_insurance` | 收到原保险合同保费取得的现金 |
| `classified_by_continuity_operation` | 按经营持续性分类 |
| `classified_by_ownership` | 按所有权归属分类 |
| `contract_work` | 工程施工 |
| `credit_asset_impairment` | 信用资产减值损失 |
| `deferred_expense` | 待摊费用 |
| `deposits_of_interbank` | 同业及其他金融机构存放款项 |
| `derivative_financial_liabilities` | 衍生金融负债 |
| `engineer_material` | 工程物资 |
| `ev_to_ebitda_ttm` | 企业倍数ttm,企业价值ttm |
| `financial_lease_receivable` | 应收融资租赁款 |
| `goodwill` | 商誉 |
| `independent_account_assets` | 独立账户资产 |
| `insurer_deposit_investment` | 保户储金及投资款 |
| `interest_income` | 利息收入 |
| `long_term_deferred_expenses` | 长期待摊费用 |
| `net_commission_income` | 手续费及佣金净收入 |
| `net_increase_from_disposing_financial_assets` | 处置交易性金融资产净增加额 |
| `net_increase_in_pledge_loans` | 质押贷款净增加额 |
| `net_interest_income` | 利息净收入 |
| `non_current_asset_due_one_year` | 一年内到期的非流动资产 |
| `non_operating_revenue` | 营业外收入 |
| `other_equity_instruments_change` | 其他权益工具投资公允价值变动 |
| `other_illiquidy_financial_assets` | 其他非流动金融资产 |
| `other_income_equity_unclassified_income_statement` | 权益法下在被投资单位不能重分类进损益表的其他综合收益中享有的份额 |
| `other_reserves` | 其他储备 |
| `perpetual_equity_debt` | 永续债(其他权益工具) |
| `proxy_security_proceeds` | 代理买卖证券款 |
| `refunds_of_taxes` | 收到的税费返还 |
| `reinsurance_cost` | 分保费用 |
| `reinsurance_income` | 分保费收入 |
| `subrogation_fee_receivable` | 应收代位追偿款 |

### 本地状态 `unknown` — 2 个

| 字段 | 名称 |
| --- | --- |
| `contract_liabilities` | 合同负债 |
| `net_profit_parent_company` | 归属母公司净利润 |

### 本地状态 `local_derived` — 2 个

| 字段 | 名称 |
| --- | --- |
| `ev_no_cash_to_ebit_lyr` | 企业倍数(不含货币资金)lyr,企业价值lyr |
| `ev_to_ebitda_lyr` | 企业倍数lyr,企业价值lyr |

### 本地状态 `local_proxy` — 1 个

| 字段 | 名称 |
| --- | --- |
| `deferred_expense_amortization` | 长期待摊费用摊销 |

## 回测目录里完全没碰过的（按表）

| 表 | 完全没碰 |
| --- | ---: |
| fields-cal-date.md | 196 |
| fields-cal-mins.md | 35 |
| fields-income-statement.md | 34 |
| fields-balance-sheet.md | 30 |
| fields-financial-derived.md | 29 |
| fields-operating-derived.md | 23 |
| fields-cashflow-statement.md | 15 |
| fields-growth-derived.md | 15 |
| fields-cashflow-derived.md | 9 |
| fields-barra.md | 5 |
| fields-valuation.md | 4 |
| fields-volume-indicators.md | 2 |
