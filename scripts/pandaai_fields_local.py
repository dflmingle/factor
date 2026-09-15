#!/usr/bin/env python3
"""Lazy local implementation of PandaAI formula-mode fields.

The bundled PandaAI field reference is the source of truth for the formula
universe.  This module only implements fields that can be reconstructed from
the local Tushare cache and keeps the rest visible in an explicit coverage
report.  Financial values are selected by announcement date, so a field never
uses a report that was not public on the signal date.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Iterable

import numpy as np
import pandas as pd
import torch

from alphagen.data.expression import Expression


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REFERENCE = PROJECT_ROOT / "vendor" / "skill-pandaai-factor-online" / "references" / "fields.md"
EXPECTED_PLATFORM_FIELD_COUNT = 348

_FIELD_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*(.*?)\s*\|\s*$")
_PERIOD_SUFFIX = re.compile(
    r"^(?P<base>.+)_(?P<period>lyr|ttm|mrq_(?:[1-9]|1[0-2]))$"
)


@dataclass(frozen=True)
class PandaAIFieldSpec:
    name: str
    label: str
    category: str


@dataclass(frozen=True)
class SourceSpec:
    endpoint: str
    column: str
    status: str = "local_direct"
    note: str = ""


def load_platform_field_specs(reference: Path = DEFAULT_REFERENCE) -> tuple[PandaAIFieldSpec, ...]:
    """Parse the formula-mode section instead of duplicating the field list."""
    if not reference.exists():
        raise FileNotFoundError(f"PandaAI field reference is missing: {reference}")

    in_formula_section = False
    category = ""
    specs: list[PandaAIFieldSpec] = []
    for line in reference.read_text(encoding="utf-8").splitlines():
        if line.startswith("## Formula-mode base fields"):
            in_formula_section = True
            continue
        if not in_formula_section:
            continue
        if line.startswith("## "):
            heading = line[3:].strip().lower()
            if "price" in heading or "volume" in heading:
                category = "price_volume"
            elif "fundamental" in heading:
                category = "fundamental"
            continue
        match = _FIELD_ROW.match(line)
        if match is None:
            continue
        name, label = match.groups()
        if name == "Field":
            continue
        specs.append(PandaAIFieldSpec(name.lower(), label, category or "unknown"))

    if len(specs) != EXPECTED_PLATFORM_FIELD_COUNT:
        raise RuntimeError(
            f"Expected {EXPECTED_PLATFORM_FIELD_COUNT} PandaAI formula fields, found {len(specs)} "
            f"in {reference}"
        )
    names = [spec.name for spec in specs]
    if len(set(names)) != len(names):
        duplicates = sorted({name for name in names if names.count(name) > 1})
        raise RuntimeError(f"Duplicate PandaAI formula fields: {duplicates}")
    return tuple(specs)


PLATFORM_FIELD_SPECS = load_platform_field_specs()
PLATFORM_FIELD_NAMES = tuple(spec.name for spec in PLATFORM_FIELD_SPECS)
PLATFORM_FIELD_SET = frozenset(PLATFORM_FIELD_NAMES)
PLATFORM_FIELD_LABELS = {spec.name: spec.label for spec in PLATFORM_FIELD_SPECS}
PRICE_VOLUME_FIELDS = frozenset(
    spec.name for spec in PLATFORM_FIELD_SPECS if spec.category == "price_volume"
)

VALUATION_FIELD_NAMES = frozenset(
    {
        "pb_ratio_lyr",
        "pb_ratio_ttm",
        "pb_ratio_lf",
        "book_to_market_ratio_lyr",
        "book_to_market_ratio_ttm",
        "book_to_market_ratio_lf",
        "dividend_yield_ttm",
        "peg_ratio_lyr",
        "peg_ratio_ttm",
        "ps_ratio_lyr",
        "ps_ratio_ttm",
        "sp_ratio_lyr",
        "sp_ratio_ttm",
        "market_cap_3",
        "a_share_market_val",
        "a_share_market_val_in_circulation",
        "ev_lyr",
        "ev_ttm",
        "ev_lf",
        "ev_no_cash_lyr",
        "ev_no_cash_ttm",
        "ev_no_cash_lf",
        "ev_to_ebitda_lyr",
        "ev_to_ebitda_ttm",
        "ev_no_cash_to_ebit_lyr",
        "ev_no_cash_to_ebit_ttm",
    }
)

STATEMENT_FIELD_NAMES = frozenset(PLATFORM_FIELD_SET - PRICE_VOLUME_FIELDS - VALUATION_FIELD_NAMES)
PERIOD_VARIANT_SUFFIXES = ("lyr", "ttm", *(f"mrq_{index}" for index in range(1, 13)))


def formula_field_name_set(
    *,
    include_period_variants: bool = True,
    include_mrq_variants: bool = True,
) -> frozenset[str]:
    """Return lower-case names accepted by the local PandaAI formula parser.

    The 348 base names come from the checked-in PandaAI reference.  Statement
    fields additionally expose the documented fiscal-year, TTM, and most
    recent-report variants.  Valuation names already contain their period in
    the base name and are therefore not expanded again.
    """
    names = set(PLATFORM_FIELD_NAMES)
    if not include_period_variants:
        return frozenset(names)
    suffixes = ("lyr", "ttm")
    if include_mrq_variants:
        suffixes += PERIOD_VARIANT_SUFFIXES[2:]
    for base in STATEMENT_FIELD_NAMES:
        names.update(f"{base}_{suffix}" for suffix in suffixes)
    return frozenset(names)


def split_formula_field_name(name: str) -> tuple[str, str]:
    """Split a formula field into its base name and period selector."""
    normalized = str(name).strip().lower()
    match = _PERIOD_SUFFIX.match(normalized)
    if match and match.group("base") in PLATFORM_FIELD_SET:
        return match.group("base"), match.group("period")
    return normalized, "current"


# Tushare statement field names are abbreviated and do not always match the
# platform's English labels.  These aliases cover the full statement family;
# a source is usable only when the requested column is present in the local
# cache, so an old narrow cache remains safe.
_SOURCE_PAIRS: dict[str, tuple[str, str]] = {
    # Income statement.
    "revenue": ("income", "total_revenue"),
    "operating_revenue": ("income", "revenue"),
    "net_interest_income": ("income", "int_income"),
    "net_commission_income": ("income", "n_commis_income"),
    "commission_income": ("income", "comm_income"),
    "commission_expense": ("income", "comm_exp"),
    "net_proxy_security_income": ("income", "n_sec_tb_income"),
    "sub_issue_security_income": ("income", "n_sec_uw_income"),
    "net_trust_income": ("income", "n_asset_mg_income"),
    "earned_premiums": ("income", "prem_earned"),
    "premiums_income": ("income", "prem_income"),
    "reinsurance_income": ("income", "reins_income"),
    "reinsurance": ("income", "out_prem"),
    "unearned_premium_reserve": ("income", "une_prem_reser"),
    "total_expense": ("income", "total_cogs"),
    "refunded_premiums": ("income", "prem_refund"),
    "compensation_expense": ("income", "compens_payout"),
    "amortization_expense": ("income", "compens_payout_refu"),
    "premium_reserve": ("income", "reser_insur_liab"),
    "amortization_premium_reserve": ("income", "insur_reser_refu"),
    "policy_dividend_payout": ("income", "div_payt"),
    "reinsurance_cost": ("income", "reins_exp"),
    "other_operating_revenue": ("income", "oth_b_income"),
    "other_operating_cost": ("income", "other_bus_cost"),
    "r_n_d": ("income", "rd_exp"),
    "other_net_income": ("income", "n_oth_income"),
    "net_open_hedge_income": ("income", "net_expo_hedging_benefits"),
    "other_revenue": ("income", "oth_income"),
    "credit_asset_impairment": ("income", "credit_impa_loss"),
    "o_n_a_expense": ("income", "admin_exp"),
    "amortization_reinsurance_cost": ("income", "reins_cost_refund"),
    "insurance_commission_expense": ("income", "comm_exp"),
    "disposal_income_on_asset": ("income", "asset_disp_income"),
    "cost_of_goods_sold": ("income", "oper_cost"),
    "sales_tax": ("income", "biz_tax_surchg"),
    "selling_expense": ("income", "sell_exp"),
    "ga_expense": ("income", "admin_exp"),
    "financing_expense": ("income", "fin_exp"),
    "financing_interest_income": ("income", "fin_exp_int_inc"),
    "financing_interest_expense": ("income", "fin_exp_int_exp"),
    "exchange_gains_or_losses": ("income", "forex_gain"),
    "profit_from_operation": ("income", "operate_profit"),
    "invest_income_associates": ("income", "ass_invest_income"),
    "fair_value_change_income": ("income", "fv_value_chg_gain"),
    "investment_income": ("income", "invest_income"),
    "asset_impairment": ("income", "assets_impair_loss"),
    "interest_income": ("income", "int_income"),
    "interest_expense": ("income", "int_exp"),
    "non_operating_revenue": ("income", "non_oper_income"),
    "non_operating_expense": ("income", "non_oper_exp"),
    "disposal_loss_on_asset": ("income", "nca_disploss"),
    "profit_before_tax": ("income", "total_profit"),
    "income_tax": ("income", "income_tax"),
    "net_profit": ("income", "n_income"),
    "non_recurring_pnl": ("fina_indicator", "extra_item"),
    "net_profit_deduct_non_recurring_pnl": ("fina_indicator", "profit_dedt"),
    "continuous_operation_net_profit": ("income", "continued_net_profit"),
    "discontinued_operation_net_profit": ("income", "end_net_profit"),
    "net_profit_parent_company": ("income", "n_income_attr_p"),
    "minority_profit": ("income", "minority_gain"),
    "other_income": ("income", "oth_compr_income"),
    "foreign_currency_statement_converted_difference": ("balancesheet", "forex_differ"),
    "total_income": ("income", "t_compr_income"),
    "total_income_parent_company": ("income", "compr_inc_attr_p"),
    "total_income_minority": ("income", "compr_inc_attr_m_s"),
    "basic_earnings_per_share": ("income", "basic_eps"),
    "fully_diluted_earnings_per_share": ("income", "diluted_eps"),
    "adjust_asset_impairment": ("income", "assets_impair_loss"),
    "adjust_credit_asset_impairment": ("income", "credit_impa_loss"),
    # Cash-flow statement.
    "cash_received_from_sales_of_goods": ("cashflow", "c_fr_sale_sg"),
    "refunds_of_taxes": ("cashflow", "recp_tax_rends"),
    "net_deposit_increase": ("cashflow", "n_depos_incr_fi"),
    "net_increase_from_central_bank": ("cashflow", "n_incr_loans_cb"),
    "net_increase_from_other_financial_institutions": ("cashflow", "n_inc_borr_oth_fi"),
    "cash_received_from_interests_and_commissions": ("cashflow", "ifc_cash_incr"),
    "net_increase_from_disposing_financial_assets": ("cashflow", "n_incr_disp_tfa"),
    "net_increase_from_repurchasing_business": ("cashflow", "n_cap_incr_repur"),
    "cash_received_from_original_insurance": ("cashflow", "prem_fr_orig_contr"),
    "cash_received_from_reinsurance": ("cashflow", "n_reinsur_prem"),
    "net_increase_from_insurer_deposit_investment": ("cashflow", "n_incr_insured_dep"),
    "net_increase_from_financial_institutions": ("cashflow", "n_incr_loans_oth_bank"),
    "cash_received_from_proxy_security": ("cashflow", "net_cash_rece_sec"),
    "cash_received_from_sub_issue_security": ("cashflow", "net_cash_rece_sec"),
    "cash_from_other_operating_activities": ("cashflow", "c_fr_oth_operate_a"),
    "cash_from_operating_activities": ("cashflow", "c_inf_fr_operate_a"),
    "cash_paid_for_goods_and_services": ("cashflow", "c_paid_goods_s"),
    "assets_depreciation_reserves": ("cashflow", "prov_depr_assets"),
    "exchange_rate_change_effect": ("cashflow", "eff_fx_flu_cash"),
    "other_effecting_cash_equivalent_items": ("cashflow", "others"),
    "cash_equivalent_increase": ("cashflow", "n_incr_cash_cash_equ"),
    "begin_period_cash_equivalent": ("cashflow", "c_cash_equ_beg_period"),
    "end_period_cash_equivalent": ("cashflow", "c_cash_equ_end_period"),
    "cash_paid_for_employee": ("cashflow", "c_paid_to_for_empl"),
    "cash_paid_for_taxes": ("cashflow", "c_paid_for_taxes"),
    "net_increase_from_loans_and_advances": ("cashflow", "n_incr_clt_loan_adv"),
    "net_increase_from_central_bank_and_banks": ("cashflow", "n_incr_dep_cbob"),
    "net_increase_from_lending_capital": ("cashflow", "net_dism_capital_add"),
    "cash_paid_for_comissions": ("cashflow", "pay_handling_chrg"),
    "cash_paid_for_orignal_insurance": ("cashflow", "c_pay_claims_orig_inco"),
    "cash_paid_for_policy_dividends": ("cashflow", "pay_comm_insur_plcy"),
    "net_increase_from_trading_financial_assets": ("cashflow", "n_incr_disp_tfa"),
    "net_increase_from_operating_buy_back": ("cashflow", "n_cap_incr_repur"),
    "cash_paid_for_other_operation_activities": ("cashflow", "oth_cash_pay_oper_act"),
    "cash_paid_for_operation_activities": ("cashflow", "st_cash_out_act"),
    "cash_flow_from_operating_activities": ("cashflow", "n_cashflow_act"),
    "cash_received_from_investment": ("cashflow", "c_recp_return_invest"),
    "cash_received_from_disposal_of_asset": ("cashflow", "n_recp_disp_fiolta"),
    "cash_received_from_other_investment_activities": ("cashflow", "oth_recp_ral_inv_act"),
    "cash_received_from_investment_activities": ("cashflow", "stot_inflows_inv_act"),
    "cash_paid_for_asset": ("cashflow", "c_pay_acq_const_fiolta"),
    "cash_paid_to_acquire_investment": ("cashflow", "c_paid_invest"),
    "cash_paid_for_other_investment_activities": ("cashflow", "oth_pay_ral_inv_act"),
    "cash_paid_for_investment_activities": ("cashflow", "stot_out_inv_act"),
    "cash_flow_from_investing_activities": ("cashflow", "n_cashflow_inv_act"),
    "cash_received_from_investors": ("cashflow", "c_recp_cap_contrib"),
    "cash_received_from_minority_invest_subsidiaries": ("cashflow", "incl_cash_rec_saims"),
    "cash_received_from_issuing_security": ("cashflow", "proc_issue_bonds"),
    "cash_received_from_financial_institution_borrows": ("cashflow", "c_recp_borrow"),
    "cash_received_from_issuing_equity_instruments": ("cashflow", "c_recp_cap_contrib"),
    "net_increase_from__financing_buy_back": ("cashflow", "n_cap_incr_repur"),
    "cash_received_from_other_financing_activities": ("cashflow", "oth_cash_recp_ral_fnc_act"),
    "cash_received_from_financing_activities": ("cashflow", "stot_cash_in_fnc_act"),
    "cash_paid_for_debt": ("cashflow", "c_prepay_amt_borr"),
    "cash_paid_for_dividend_and_interest": ("cashflow", "c_pay_dist_dpcp_int_exp"),
    "dividends_paid_to_minority_by_subsidiaries": ("cashflow", "incl_dvd_profit_paid_sc_ms"),
    "cash_paid_for_other_financing_activities": ("cashflow", "oth_cashpay_ral_fnc_act"),
    "cash_paid_to_financing_activities": ("cashflow", "stot_cashout_fnc_act"),
    "cash_flow_from_financing_activities": ("cashflow", "n_cash_flows_fnc_act"),
    "net_cash_deal_from_sub": ("cashflow", "n_recp_disp_sobu"),
    "net_cash_payment_from_sub": ("cashflow", "n_disp_subs_oth_biz"),
    "net_increase_in_pledge_loans": ("cashflow", "n_incr_pledge_loan"),
    "net_increase_from_investing_buy_back": ("cashflow", "n_cap_incr_repur"),
    "net_inc_cash_and_equivalents": ("cashflow", "n_incr_cash_cash_equ"),
    "fixed_asset_depreciation": ("cashflow", "depr_fa_coga_dpba"),
    "deferred_expense_amortization": ("cashflow", "lt_amort_deferred_exp"),
    "intangible_asset_amortization": ("cashflow", "amort_intang_assets"),
    "others": ("cashflow", "others"),
    # Balance sheet.
    "financial_asset_held_for_trading": ("balancesheet", "trad_asset"),
    "cash_equivalent": ("balancesheet", "money_cap"),
    "client_deposits": ("balancesheet", "client_depos"),
    "bill_receivable": ("balancesheet", "notes_receiv"),
    "dividend_receivable": ("balancesheet", "div_receiv"),
    "bill_accts_receivable": ("balancesheet", "accounts_receiv_bill"),
    "interest_receivable": ("balancesheet", "int_receiv"),
    "net_accts_receivable": ("balancesheet", "accounts_receiv"),
    "contract_assets": ("balancesheet", "contract_assets"),
    "prepayment": ("balancesheet", "prepayment"),
    "financial_receivable": ("balancesheet", "receiv_financing"),
    "financial_lease_receivable": ("balancesheet", "lt_rec"),
    "other_equity_investment": ("balancesheet", "oth_eq_invest"),
    "other_illiquidy_financial_assets": ("balancesheet", "oth_illiq_fin_assets"),
    "non_current_asset_due_one_year": ("balancesheet", "nca_within_1y"),
    "other_receivables_interest_dividend": ("balancesheet", "oth_receiv"),
    "inventory": ("balancesheet", "inventories"),
    "deferred_expense": ("balancesheet", "amor_exp"),
    "assets_hold_for_sale": ("balancesheet", "hfs_assets"),
    "contract_work": ("balancesheet", "cip_total"),
    "other_current_assets": ("balancesheet", "oth_cur_assets"),
    "current_assets": ("balancesheet", "total_cur_assets"),
    "financial_asset_available_for_sale": ("balancesheet", "fa_avail_for_sale"),
    "non_current_liability_due_one_year": ("balancesheet", "non_cur_liab_due_1y"),
    "debt_investment": ("balancesheet", "debt_invest"),
    "other_debt_investment": ("balancesheet", "oth_debt_invest"),
    "financial_asset_hold_to_maturity": ("balancesheet", "htm_invest"),
    "real_estate_investment": ("balancesheet", "invest_real_estate"),
    "long_term_receivables": ("balancesheet", "lt_rec"),
    "net_long_term_equity_investment": ("balancesheet", "lt_eqt_invest"),
    "net_fixed_assets": ("balancesheet", "fix_assets"),
    "total_fixed_assets": ("balancesheet", "fix_assets_total"),
    "engineer_material": ("balancesheet", "const_materials"),
    "construction_in_progress": ("balancesheet", "cip"),
    "total_construction_in_progress": ("balancesheet", "cip_total"),
    "fixed_asset_to_be_disposed": ("balancesheet", "fixed_assets_disp"),
    "capitalized_biological_assets": ("balancesheet", "produc_bio_assets"),
    "oil_and_gas_assets": ("balancesheet", "oil_and_gas_assets"),
    "intangible_assets": ("balancesheet", "intan_assets"),
    "impairment_intangible_assets": ("balancesheet", "r_and_d"),
    "seat_costs": ("balancesheet", "transac_seat_fee"),
    "use_right_assets": ("balancesheet", "use_right_assets"),
    "goodwill": ("balancesheet", "goodwill"),
    "long_term_deferred_expenses": ("balancesheet", "lt_amor_exp"),
    "deferred_income_tax_assets": ("balancesheet", "defer_tax_assets"),
    "other_non_current_assets": ("balancesheet", "oth_nca"),
    "non_current_assets": ("balancesheet", "total_nca"),
    "loan_account_receivables": ("balancesheet", "loanto_oth_bank_fi"),
    "fund_providing": ("balancesheet", "lending_funds"),
    "reinsurance_reserve_receivable": ("balancesheet", "reinsur_res_receiv"),
    "settlement_provision": ("balancesheet", "sett_rsrv"),
    "client_provision": ("balancesheet", "client_prov"),
    "interbank_deposits": ("balancesheet", "depos_ib_deposits"),
    "precious_metals": ("balancesheet", "prec_metals"),
    "lend_capital": ("balancesheet", "loanto_oth_bank_fi"),
    "derivative_financial_assets": ("balancesheet", "deriv_assets"),
    "resale_financial_assets": ("balancesheet", "pur_resale_fa"),
    "loans_advances_to_customers": ("balancesheet", "decr_in_disbur"),
    "insurance_receivable": ("balancesheet", "premium_receiv"),
    "reinsurance_receivable": ("balancesheet", "reinsur_receiv"),
    "unearned_reserve_receivable": ("balancesheet", "rr_reins_une_prem"),
    "unclaimed_reserve_receivable": ("balancesheet", "rr_reins_outstd_cla"),
    "life_reserve_receivable": ("balancesheet", "rr_reins_lins_liab"),
    "health_reserve_receivable": ("balancesheet", "rr_reins_lthins_liab"),
    "insurer_mortgage_loan": ("balancesheet", "ph_pledge_loans"),
    "fixed_deposits": ("balancesheet", "time_deposits"),
    "refundable_deposits": ("balancesheet", "refund_depos"),
    "refundable_capital_deposits": ("balancesheet", "refund_cap_depos"),
    "independent_account_assets": ("balancesheet", "indep_acct_assets"),
    "other_assets": ("balancesheet", "oth_assets"),
    "other_accts_receivable": ("balancesheet", "oth_receiv"),
    "total_assets": ("balancesheet", "total_assets"),
    "mortgaged_loan": ("balancesheet", "pledge_borr"),
    "short_term_loans": ("balancesheet", "st_borr"),
    "financial_liabilities": ("balancesheet", "trading_fl"),
    "notes_payable": ("balancesheet", "notes_payable"),
    "accts_payable": ("balancesheet", "acct_payable"),
    "bill_accts_payable": ("balancesheet", "notes_payable"),
    "contract_liabilities": ("balancesheet", "contract_liab"),
    "advance_from_customers": ("balancesheet", "adv_receipts"),
    "payroll_payable": ("balancesheet", "payroll_payable"),
    "dividend_payable": ("balancesheet", "div_payable"),
    "tax_payable": ("balancesheet", "taxes_payable"),
    "interest_payable": ("balancesheet", "int_payable"),
    "other_fees_payable": ("balancesheet", "oth_payable"),
    "other_payable": ("balancesheet", "oth_payable"),
    "other_payable_interest_dividend": ("balancesheet", "oth_payable"),
    "short_term_debt": ("balancesheet", "st_bonds_payable"),
    "accrued_expense": ("balancesheet", "acc_exp"),
    "liabilities_hold_for_sale": ("balancesheet", "hfs_sales"),
    "estimated_liabilities": ("balancesheet", "estimated_liab"),
    "deferred_income": ("balancesheet", "deferred_inc"),
    "long_term_liabilities_due_one_year": ("balancesheet", "non_cur_liab_due_1y"),
    "other_current_liabilities": ("balancesheet", "oth_cur_liab"),
    "current_liabilities": ("balancesheet", "total_cur_liab"),
    "long_term_loans": ("balancesheet", "lt_borr"),
    "bond_payable": ("balancesheet", "bond_payable"),
    "perpetual_bond": ("balancesheet", "bond_payable"),
    "preference_shares": ("balancesheet", "oth_eqt_tools_p_shr"),
    "long_term_payable": ("balancesheet", "lt_payable"),
    "accrued_staff_costs": ("balancesheet", "lt_payroll_payable"),
    "grants_received": ("balancesheet", "specific_payables"),
    "deferred_income_tax_liabilities": ("balancesheet", "defer_tax_liab"),
    "lease_liabilities": ("balancesheet", "lease_liab"),
    "other_non_current_liabilities": ("balancesheet", "oth_ncl"),
    "non_current_liabilities": ("balancesheet", "total_ncl"),
    "borrowings_from_central_banks": ("balancesheet", "cb_borr"),
    "deposits_of_interbank": ("balancesheet", "depos_ib_deposits"),
    "borrowings_capital": ("balancesheet", "loan_oth_bank"),
    "derivative_financial_liabilities": ("balancesheet", "deriv_liab"),
    "buy_back_security_proceeds": ("balancesheet", "sold_for_repur_fa"),
    "deposits": ("balancesheet", "depos"),
    "proxy_security_proceeds": ("balancesheet", "acting_trading_sec"),
    "sub_issue_security_proceeds": ("balancesheet", "acting_uw_sec"),
    "security_deposits_received": ("balancesheet", "depos_received"),
    "advance_insurance": ("balancesheet", "prem_receiv_adva"),
    "comission_payable": ("balancesheet", "comm_payable"),
    "reinsurance_payable": ("balancesheet", "payable_to_reinsurer"),
    "compensation_payable": ("balancesheet", "indem_payable"),
    "policy_dividend_payable": ("balancesheet", "policy_div_payable"),
    "deposits_from_interbank": ("balancesheet", "depos_oth_bfi"),
    "insurance_contract_reserve": ("balancesheet", "rsrv_insur_cont"),
    "insurer_deposit_investment": ("balancesheet", "ph_invest"),
    "uncertained_premium_reserve": ("balancesheet", "reser_une_prem"),
    "unclaimed_indemnity_reserve": ("balancesheet", "reser_outstd_claims"),
    "life_insurance_reserve": ("balancesheet", "reser_lins_liab"),
    "health_insurance_reserve": ("balancesheet", "reser_lthins_liab"),
    "independent_account_liabilities": ("balancesheet", "indept_acc_liab"),
    "other_liabilities": ("balancesheet", "oth_liab"),
    "deferred_revenue": ("balancesheet", "deferred_inc"),
    "total_liabilities": ("balancesheet", "total_liab"),
    "paid_in_capital": ("balancesheet", "total_share"),
    "other_equity_instruments": ("balancesheet", "oth_eqt_tools"),
    "equity_preferred_stock": ("balancesheet", "oth_eqt_tools_p_shr"),
    "perpetual_equity_debt": ("balancesheet", "oth_eqt_tools"),
    "capital_reserve": ("balancesheet", "cap_rese"),
    "surplus_reserve": ("balancesheet", "surplus_rese"),
    "undistributed_profit": ("balancesheet", "undistr_porfit"),
    "treasury_stock": ("balancesheet", "treasury_share"),
    "equity_parent_company": ("balancesheet", "total_hldr_eqy_exc_min_int"),
    "total_equity": ("balancesheet", "total_hldr_eqy_inc_min_int"),
    "general_reserve": ("balancesheet", "ordin_risk_reser"),
    "foreign_currency_converted_difference": ("balancesheet", "forex_differ"),
    "uncertained_impairment_losses": ("cashflow", "uncon_invest_loss"),
    "other_reserves": ("balancesheet", "oth_comp_income"),
    "specific_reserve": ("balancesheet", "special_rese"),
    "minority_interest": ("balancesheet", "minority_int"),
    "total_equity_and_liabilities": ("balancesheet", "total_liab_hldr_eqy"),
    # Tushare exposes these items in broader buckets. Keep them usable for
    # local exploration while marking the mapping as a proxy below.
    "cash_flow_hedging_effective_portion": ("income", "net_expo_hedging_benefits"),
    "other_income_unclassified_income_statement": ("income", "oth_compr_income"),
    "other_income_classified_income_statement": ("income", "oth_compr_income"),
    "other_income_equity_unclassified_income_statement": ("income", "compr_inc_attr_p"),
    "other_income_equity_classified_income_statement": ("income", "compr_inc_attr_p"),
    "other_income_minority": ("income", "compr_inc_attr_m_s"),
    "other_equity_instruments_change": ("income", "oth_compr_income"),
    "corporate_credit_risk_change": ("income", "net_expo_hedging_benefits"),
    "other_debt_investment_change": ("income", "oth_compr_income"),
    "other_debt_investment_reserve": ("income", "credit_impa_loss"),
    "trade_risk_allowances": ("balancesheet", "ordin_risk_reser"),
    "accumulated_depreciation": ("cashflow", "depr_fa_coga_dpba"),
    "assets_reclassified_other_income": ("income", "oth_compr_income"),
    "cash_paid_for_reinsurance": ("cashflow", "oth_cash_pay_oper_act"),
    "consumable_biological_assets": ("balancesheet", "produc_bio_assets"),
    "depreciation_reserve": ("cashflow", "prov_depr_assets"),
    "draw_back_canceled_loans": ("cashflow", "n_incr_clt_loan_adv"),
    "financial_asset_available_for_sale_change": ("income", "oth_compr_income"),
    "financial_asset_hold_to_maturity_change": ("income", "oth_compr_income"),
    "financial_lease_payable": ("balancesheet", "lease_liab"),
    "housing_revolving_funds": ("balancesheet", "specific_payables"),
    "remearsured_other_income": ("income", "oth_compr_income"),
    "subrogation_fee_receivable": ("balancesheet", "oth_receiv"),
}


# These aliases are useful for local research but do not assert that the
# platform's internal definition is identical to the Tushare proxy.
PROXY_FIELDS = frozenset(
    {
        "net_proxy_security_income",
        "sub_issue_security_income",
        "net_trust_income",
        "amortization_expense",
        "premium_reserve",
        "net_profit_deduct_non_recurring_pnl",
        "other_effecting_total_profits_items",
        "other_effecting_net_profits_items",
        "net_increase_from_other_financial_institutions",
        "draw_back_canceled_loans",
        "net_increase_from_repurchasing_business",
        "net_increase_from_financial_institutions",
        "cash_from_operating_activities",
        "assets_depreciation_reserves",
        "net_increase_from_loans_and_advances",
        "net_increase_from_lending_capital",
        "cash_paid_for_operation_activities",
        "cash_received_from_investment_activities",
        "cash_paid_for_investment_activities",
        "cash_received_from_minority_invest_subsidiaries",
        "cash_received_from_issuing_equity_instruments",
        "net_increase_from__financing_buy_back",
        "dividends_paid_to_minority_by_subsidiaries",
        "net_cash_deal_from_sub",
        "net_cash_payment_from_sub",
        "net_increase_in_pledge_loans",
        "net_increase_from_investing_buy_back",
        "fixed_asset_depreciation",
        "deferred_expense_amortization",
        "intangible_asset_amortization",
        "financial_receivable",
        "financial_lease_receivable",
        "contract_work",
        "total_fixed_assets",
        "total_construction_in_progress",
        "impairment_intangible_assets",
        "fund_providing",
        "loans_advances_to_customers",
        "bill_accts_payable",
        "accrued_staff_costs",
        "grants_received",
        "paid_in_capital",
        "a_share_market_val",
        "a_share_market_val_in_circulation",
        "cash_flow_hedging_effective_portion",
        "other_income_unclassified_income_statement",
        "other_income_classified_income_statement",
        "other_income_equity_unclassified_income_statement",
        "other_income_equity_classified_income_statement",
        "other_income_minority",
        "other_equity_instruments_change",
        "corporate_credit_risk_change",
        "other_debt_investment_change",
        "other_debt_investment_reserve",
        "trade_risk_allowances",
        "impairment_intangible_assets",
        "net_increase_from_investing_buy_back",
        "accumulated_depreciation",
        "assets_reclassified_other_income",
        "cash_paid_for_reinsurance",
        "consumable_biological_assets",
        "depreciation_reserve",
        "draw_back_canceled_loans",
        "financial_asset_available_for_sale_change",
        "financial_asset_hold_to_maturity_change",
        "financial_lease_payable",
        "housing_revolving_funds",
        "remearsured_other_income",
        "subrogation_fee_receivable",
    }
)


VALUATION_FIELDS = VALUATION_FIELD_NAMES


def _safe_divide(lhs: np.ndarray, rhs: np.ndarray) -> np.ndarray:
    result = np.full_like(lhs, np.nan, dtype=np.float32)
    valid = np.isfinite(lhs) & np.isfinite(rhs) & (np.abs(rhs) > 1e-12)
    result[valid] = lhs[valid] / rhs[valid]
    return result


DERIVED_FIELD_NAMES = frozenset(
    {
        "gross_profit",
        "bad_debt_reserve",
        "other_effecting_total_profits_items",
        "other_effecting_net_profits_items",
        "dividend_yield_ttm",
        "peg_ratio_lyr",
        "peg_ratio_ttm",
    }
)


def _period_suffix(period: str) -> str:
    return "" if period == "current" else f"_{period}"


class PandaAIField(Expression):
    """Expression leaf whose panel is resolved by the attached local store."""

    def __init__(self, field_name: str) -> None:
        name = str(field_name).strip().lower()
        if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
            raise ValueError(f"Invalid PandaAI field name: {field_name}")
        self.field_name = name

    def evaluate(self, data: Any, period: slice = slice(0, 1)) -> torch.Tensor:
        getter = getattr(data, "get_named_feature", None)
        if getter is None:
            raise RuntimeError("This data adapter has no PandaAI named-field store")
        return getter(self.field_name, period)

    def __str__(self) -> str:
        return self.field_name

    @property
    def is_featured(self) -> bool:
        return True


def build_pandaai_namespace(
    include_period_variants: bool = True,
    include_mrq_variants: bool = True,
) -> dict[str, PandaAIField]:
    """Return case-insensitive formula leaves for all documented fields."""
    names = formula_field_name_set(
        include_period_variants=include_period_variants,
        include_mrq_variants=include_mrq_variants,
    )
    result: dict[str, PandaAIField] = {}
    for name in sorted(names):
        leaf = PandaAIField(name)
        result[name] = leaf
        result[name.upper()] = leaf
    return result


class PandaAIFieldStore:
    """Resolve PandaAI fields against one aligned local data panel.

    Only requested field panels are materialized.  A bounded LRU keeps a GP
    population from retaining hundreds of 2-D full-A tensors at once.
    """

    def __init__(
        self,
        *,
        data: Any,
        frame: pd.DataFrame,
        financial_root: Path | None = None,
        max_cached_fields: int = 24,
    ) -> None:
        self.data = data
        self.frame = frame.copy() if not frame.empty else frame
        self.financial_root = financial_root
        self.max_cached_fields = max(1, int(max_cached_fields))
        # Keep raw real-date arrays separate from the padded tensors consumed
        # by AlphaPROBE.  Derived fields recurse through the raw cache and do
        # not depend on a tensor cache entry surviving LRU eviction.
        self._array_cache: OrderedDict[str, np.ndarray] = OrderedDict()
        self._panel_cache: OrderedDict[str, torch.Tensor] = OrderedDict()
        self._status_cache: dict[str, dict[str, Any]] = {}
        self._financial_cache: dict[str, pd.DataFrame] | None = None
        self._source_columns: dict[str, set[str]] = {}
        self._real_dates = [
            pd.Timestamp(value).normalize()
            for value in list(getattr(data, "_pre_dates", []))
            + list(getattr(data, "_evaluation_dates", []))
            + list(getattr(data, "_post_dates", []))
        ]
        self._offset = int(getattr(data, "_pre_padding", 0))
        self._n_stocks = int(data.n_stocks)
        self._stock_ids = [str(value) for value in data._stock_ids]
        self._full_length = int(data.data.shape[0])
        self._frame_indexed: pd.DataFrame | None = None

        if not self._real_dates:
            raise ValueError("PandaAI field store needs a non-empty local calendar")
        if len(self._real_dates) + self._offset > self._full_length:
            raise ValueError("Named-field calendar does not match the data adapter")

    @property
    def platform_field_count(self) -> int:
        return len(PLATFORM_FIELD_NAMES)

    def _index_frame(self) -> pd.DataFrame:
        if self._frame_indexed is None:
            frame = self.frame.copy()
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
            frame["instrument"] = frame["instrument"].astype(str)
            frame = frame.dropna(subset=["date", "instrument"])
            frame = frame.drop_duplicates(["date", "instrument"], keep="last")
            self._frame_indexed = frame.set_index(["date", "instrument"]).sort_index()
        return self._frame_indexed

    def _ensure_financial_cache(self) -> dict[str, pd.DataFrame]:
        if self._financial_cache is None:
            if self.financial_root is None:
                raise FileNotFoundError("No local financial cache was configured")
            # Import lazily so price-only runs do not need the finance module.
            from financial_factor_local import load_financial_cache

            self._financial_cache = load_financial_cache(self.financial_root)
            self._source_columns = {
                endpoint: set(frame.columns)
                for endpoint, frame in self._financial_cache.items()
            }
        return self._financial_cache

    def _daily_panel(self, column: str | tuple[str, ...], *, fill: str = "none") -> np.ndarray:
        indexed = self._index_frame()
        candidates = (column,) if isinstance(column, str) else column
        source = next((item for item in candidates if item in indexed.columns), None)
        if source is None:
            return np.full((len(self._real_dates), self._n_stocks), np.nan, dtype=np.float32)
        wide = indexed[source].unstack("instrument")
        wide = wide.reindex(index=pd.DatetimeIndex(self._real_dates), columns=self._stock_ids)
        if fill == "ffill":
            wide = wide.ffill()
        elif fill == "zero":
            wide = wide.fillna(0.0)
        return wide.to_numpy(dtype=np.float32, copy=True)

    def _report_panel(
        self,
        endpoint: str,
        column: str,
        period: str,
    ) -> np.ndarray:
        cache = self._ensure_financial_cache()
        if endpoint not in cache:
            return np.full((len(self._real_dates), self._n_stocks), np.nan, dtype=np.float32)
        table = cache[endpoint]
        source_column = column
        if period == "ttm" and endpoint in {"income", "cashflow"}:
            table = cache.get(f"{endpoint}_ttm", table)
            source_column = f"ttm_{column}"
        elif period == "lyr":
            table = table[table.get("end_type", pd.Series(index=table.index)).astype(str).eq("4")]
        if source_column not in table.columns:
            return np.full((len(self._real_dates), self._n_stocks), np.nan, dtype=np.float32)

        table = table[["instrument", "ann_date", "end_date", source_column] + [
            column for column in ["update_flag"] if column in table.columns
        ]].copy()
        table["ann_date"] = pd.to_datetime(table["ann_date"], errors="coerce").dt.normalize()
        table["end_date"] = pd.to_datetime(table["end_date"], errors="coerce").dt.normalize()
        table[source_column] = pd.to_numeric(table[source_column], errors="coerce")
        table = table.dropna(subset=["instrument", "ann_date", source_column])
        if table.empty:
            return np.full((len(self._real_dates), self._n_stocks), np.nan, dtype=np.float32)
        sort_columns = ["instrument", "ann_date", "end_date"]
        if "update_flag" in table.columns:
            sort_columns.append("update_flag")
        table = table.sort_values(sort_columns)
        # One report per announcement date is enough for an as-of lookup.  The
        # latest end date/update flag wins when a statement is restated.
        table = table.drop_duplicates(["instrument", "ann_date"], keep="last")

        result = np.full((len(self._real_dates), self._n_stocks), np.nan, dtype=np.float32)
        dates = np.asarray(self._real_dates, dtype="datetime64[ns]")
        stock_positions = {instrument: index for index, instrument in enumerate(self._stock_ids)}
        nth = None
        if period.startswith("mrq_"):
            nth = int(period.split("_", 1)[1])
        for instrument, group in table.groupby("instrument", sort=False):
            stock_position = stock_positions.get(str(instrument))
            if stock_position is None:
                continue
            group = group.sort_values("ann_date")
            announcement_dates = group["ann_date"].to_numpy(dtype="datetime64[ns]")
            values = group[source_column].to_numpy(dtype=np.float32)
            latest = np.searchsorted(announcement_dates, dates, side="right") - 1
            if nth is not None:
                latest = latest - nth + 1
            valid = latest >= 0
            result[valid, stock_position] = values[latest[valid]]
        return result

    def _source_available(self, spec: SourceSpec, period: str) -> bool:
        cache = self._ensure_financial_cache()
        table = cache.get(spec.endpoint)
        source_column = spec.column
        if period == "ttm" and spec.endpoint in {"income", "cashflow"}:
            table = cache.get(f"{spec.endpoint}_ttm")
            source_column = f"ttm_{spec.column}"
        return table is not None and source_column in table.columns

    def _daily_available(self, column: str | tuple[str, ...]) -> bool:
        indexed = self._index_frame()
        candidates = (column,) if isinstance(column, str) else column
        return any(item in indexed.columns for item in candidates)

    def _computed_status(self, base: str, period: str) -> tuple[str, str, str]:
        """Check computed-field inputs without materializing any panel."""
        if base == "market_cap_3":
            available = self._daily_available("total_mv")
            return (
                "local_direct" if available else "unavailable",
                "daily_basic.total_mv" if available else "",
                "aligned daily_basic total market value" if available else "daily_basic total_mv is absent",
            )
        if base in {"a_share_market_val", "a_share_market_val_in_circulation"}:
            column = "total_mv" if base == "a_share_market_val" else "circ_mv"
            available = self._daily_available(column)
            return (
                "local_proxy" if available else "unavailable",
                f"daily_basic.{column}" if available else "",
                "daily_basic market-value proxy for the platform A-share valuation field"
                if available
                else f"daily_basic {column} is absent",
            )
        if base == "gross_profit":
            inputs = (
                ("operating_revenue", period),
                ("cost_of_goods_sold", period),
                ("sales_tax", period),
            )
            available = all(self._field_available(name, selected_period) for name, selected_period in inputs)
            return (
                "local_proxy" if available else "unavailable",
                "income.revenue-income.oper_cost-income.biz_tax_surchg" if available else "",
                "主营业利润 proxy: operating revenue - operating cost - sales tax"
                if available
                else "derived-field inputs are not all present in the local cache",
            )
        if base == "bad_debt_reserve":
            available = self._source_present("balancesheet", "accounts_receiv", period) and self._field_available(
                "net_accts_receivable", period
            )
            return (
                "local_proxy" if available else "unavailable",
                "balancesheet.accounts_receiv - balancesheet.accounts_receiv(net)" if available else "",
                "坏账准备 proxy: 应收账款原值减应收账款净额"
                if available
                else "derived-field inputs are not all present in the local cache",
            )
        if base == "other_effecting_total_profits_items":
            columns = ["total_profit", "operate_profit", "non_oper_income", "non_oper_exp"]
            available = all(self._source_present("income", column, period) for column in columns)
            return (
                "local_proxy" if available else "unavailable",
                "income.total_profit-income.operate_profit-income.non_oper_income+income.non_oper_exp"
                if available
                else "",
                "影响利润总额的其他科目 residual proxy"
                if available
                else "derived-field inputs are not all present in the local cache",
            )
        if base == "other_effecting_net_profits_items":
            columns = ["n_income", "total_profit", "income_tax"]
            available = all(self._source_present("income", column, period) for column in columns)
            return (
                "local_proxy" if available else "unavailable",
                "income.n_income-income.total_profit+income.income_tax" if available else "",
                "影响净利润的其他科目 residual proxy"
                if available
                else "derived-field inputs are not all present in the local cache",
            )
        if base == "dividend_yield_ttm":
            available = self._source_present("income", "comshare_payable_dvd", "ttm") or self._source_present(
                "income", "prfshare_payable_dvd", "ttm"
            )
            available = available and self._daily_available("total_mv")
            return (
                "local_proxy" if available else "unavailable",
                "income_ttm.comshare_payable_dvd/prfshare_payable_dvd / daily_basic.total_mv"
                if available
                else "",
                "Tushare income-statement dividend payout proxy; not a verified platform dividend series"
                if available
                else "derived-field inputs are not all present in the local cache",
            )
        if base in {"peg_ratio_lyr", "peg_ratio_ttm"}:
            earnings_period = "lyr" if base.endswith("_lyr") else "ttm"
            available = (
                self._field_available("net_profit_parent_company", earnings_period)
                and self._source_present("fina_indicator", "netprofit_yoy", earnings_period)
                and self._daily_available("total_mv")
            )
            return (
                "local_proxy" if available else "unavailable",
                f"daily_basic.total_mv / income.{earnings_period}.n_income_attr_p / fina_indicator.{earnings_period}.netprofit_yoy"
                if available
                else "",
                "PEG proxy using Tushare net-profit growth percentage; platform denominator is not byte-equivalent"
                if available
                else "derived-field inputs are not all present in the local cache",
            )
        if base in VALUATION_FIELDS:
            available = self._field_available(base, period)
            return (
                "local_derived" if available else "unavailable",
                "PIT Tushare valuation reconstruction" if available else "",
                "valuation reconstructed from PIT statements" if available else "derived-field inputs are not all present in the local cache",
            )
        return "unavailable", "", "no local computed-field handler"

    def _source_spec(self, base: str) -> SourceSpec | None:
        pair = _SOURCE_PAIRS.get(base)
        if pair is None:
            return None
        endpoint, column = pair
        cache = self._ensure_financial_cache()
        source_columns = self._source_columns.get(endpoint, set(cache.get(endpoint, pd.DataFrame()).columns))
        if column not in source_columns:
            return None
        status = "local_proxy" if base in PROXY_FIELDS else "local_direct"
        note = "Tushare alias/proxy" if status == "local_proxy" else "PIT Tushare statement field"
        return SourceSpec(endpoint, column, status, note)

    def _source_present(self, endpoint: str, column: str, period: str) -> bool:
        cache = self._ensure_financial_cache()
        table = cache.get(endpoint)
        source_column = column
        if period == "ttm" and endpoint in {"income", "cashflow"}:
            table = cache.get(f"{endpoint}_ttm")
            source_column = f"ttm_{column}"
        return table is not None and source_column in table.columns

    def _field_available(self, base: str, period: str) -> bool:
        if base in {"open", "close", "high", "low"}:
            return self._daily_available(
                {
                    "open": ("open_qfq", "open"),
                    "close": ("close_qfq", "close"),
                    "high": ("high_qfq", "high"),
                    "low": ("low_qfq", "low"),
                }[base]
            )
        if base == "volume":
            return self._daily_available("volume")
        if base == "amount":
            return self._daily_available("amount")
        if base == "turnover":
            return self._daily_available("turnover")
        if base in {"market_cap", "market_cap_3"}:
            return self._daily_available("total_mv")
        if base == "a_share_market_val":
            return self._daily_available("total_mv")
        if base == "a_share_market_val_in_circulation":
            return self._daily_available("circ_mv")
        if base in DERIVED_FIELD_NAMES:
            return self._computed_status(base, period)[0] != "unavailable"
        if base in VALUATION_FIELDS:
            valuation: dict[str, tuple[str, str]] = {
                "pb_ratio_lyr": ("market_cap", "equity_parent_company_lyr"),
                "pb_ratio_ttm": ("market_cap", "equity_parent_company_ttm"),
                "pb_ratio_lf": ("market_cap", "equity_parent_company"),
                "book_to_market_ratio_lyr": ("equity_parent_company_lyr", "market_cap"),
                "book_to_market_ratio_ttm": ("equity_parent_company_ttm", "market_cap"),
                "book_to_market_ratio_lf": ("equity_parent_company", "market_cap"),
                "ps_ratio_lyr": ("market_cap", "revenue_lyr"),
                "ps_ratio_ttm": ("market_cap", "revenue_ttm"),
                "sp_ratio_lyr": ("revenue_lyr", "market_cap"),
                "sp_ratio_ttm": ("revenue_ttm", "market_cap"),
                "ev_lyr": ("market_cap", "total_liabilities_lyr"),
                "ev_ttm": ("market_cap", "total_liabilities_ttm"),
                "ev_lf": ("market_cap", "total_liabilities"),
                "ev_no_cash_lyr": ("ev_lyr", "cash_equivalent_lyr"),
                "ev_no_cash_ttm": ("ev_ttm", "cash_equivalent_ttm"),
                "ev_no_cash_lf": ("ev_lf", "cash_equivalent"),
                "ev_to_ebitda_lyr": ("ev_lyr", "ebitda_lyr"),
                "ev_to_ebitda_ttm": ("ev_ttm", "ebitda_ttm"),
                "ev_no_cash_to_ebit_lyr": ("ev_no_cash_lyr", "ebit_lyr"),
                "ev_no_cash_to_ebit_ttm": ("ev_no_cash_ttm", "ebit_ttm"),
            }
            if base == "market_cap_3":
                return self._daily_available("total_mv")
            if base in {"dividend_yield_ttm", "peg_ratio_lyr", "peg_ratio_ttm"}:
                return self._computed_status(base, period)[0] != "unavailable"
            if base in {"a_share_market_val", "a_share_market_val_in_circulation"}:
                return self._field_available(base, period)
            if base in valuation:
                lhs, rhs = valuation[base]
                return self._field_available(*split_formula_field_name(lhs)) and self._field_available(
                    *split_formula_field_name(rhs)
                )
        spec = _SOURCE_PAIRS.get(base)
        return spec is not None and self._source_present(spec[0], spec[1], period)

    def _indicator_panel(self, column: str, period: str = "current") -> np.ndarray:
        cache = self._ensure_financial_cache()
        table = cache.get("fina_indicator")
        if table is None or column not in table.columns:
            raise KeyError(f"No local fina_indicator source for {column}")
        return self._report_panel("fina_indicator", column, period)

    def _derived_panel(self, base: str, period: str) -> tuple[np.ndarray, str, str, str]:
        suffix = _period_suffix(period)
        if base == "gross_profit":
            revenue = self._named_array(f"operating_revenue{suffix}")
            cost = self._named_array(f"cost_of_goods_sold{suffix}")
            tax = self._named_array(f"sales_tax{suffix}")
            return (
                revenue - cost - tax,
                "local_derived",
                "income.revenue-income.oper_cost-income.biz_tax_surchg",
                "主营业利润 proxy: operating revenue - operating cost - sales tax",
            )
        if base == "bad_debt_reserve":
            gross = self._report_panel("balancesheet", "accounts_receiv", period)
            net = self._named_array(f"net_accts_receivable{suffix}")
            return (
                gross - net,
                "local_proxy",
                "balancesheet.accounts_receiv - balancesheet.accounts_receiv(net)",
                "坏账准备 proxy: 应收账款原值减应收账款净额",
            )
        if base == "other_effecting_total_profits_items":
            total_profit = self._report_panel("income", "total_profit", period)
            operating_profit = self._report_panel("income", "operate_profit", period)
            non_operating_revenue = self._report_panel("income", "non_oper_income", period)
            non_operating_expense = self._report_panel("income", "non_oper_exp", period)
            return (
                total_profit - operating_profit - non_operating_revenue + non_operating_expense,
                "local_proxy",
                "income.total_profit-income.operate_profit-income.non_oper_income+income.non_oper_exp",
                "影响利润总额的其他科目 residual proxy",
            )
        if base == "other_effecting_net_profits_items":
            net_profit = self._report_panel("income", "n_income", period)
            total_profit = self._report_panel("income", "total_profit", period)
            income_tax = self._report_panel("income", "income_tax", period)
            return (
                net_profit - total_profit + income_tax,
                "local_proxy",
                "income.n_income-income.total_profit+income.income_tax",
                "影响净利润的其他科目 residual proxy",
            )
        if base == "dividend_yield_ttm":
            components = []
            for column in ("comshare_payable_dvd", "prfshare_payable_dvd"):
                panel = self._report_panel("income", column, "ttm")
                if np.isfinite(panel).any():
                    components.append(panel)
            if not components:
                raise KeyError("No PIT dividend payout source is available")
            numerator = np.zeros_like(components[0], dtype=np.float32)
            for component in components:
                numerator = numerator + component
            return (
                _safe_divide(numerator, self._named_array("market_cap")),
                "local_proxy",
                "income_ttm.comshare_payable_dvd/prfshare_payable_dvd / daily_basic.total_mv",
                "Tushare income-statement dividend payout proxy; not a verified platform dividend series",
            )
        if base in {"peg_ratio_lyr", "peg_ratio_ttm"}:
            earnings_period = "lyr" if base.endswith("_lyr") else "ttm"
            earnings = self._named_array(f"net_profit_parent_company_{earnings_period}")
            growth = self._indicator_panel("netprofit_yoy", earnings_period)
            pe = _safe_divide(self._named_array("market_cap"), earnings)
            return (
                _safe_divide(pe, growth),
                "local_proxy",
                f"daily_basic.total_mv / income.{earnings_period}.n_income_attr_p / fina_indicator.{earnings_period}.netprofit_yoy",
                "PEG proxy using Tushare net-profit growth percentage; platform denominator is not byte-equivalent",
            )
        raise KeyError(f"No local derived field handler for {base}")

    def _base_panel(self, base: str, period: str) -> tuple[np.ndarray, str, str, str]:
        # Price and daily_basic fields use the same aligned panel as the score.
        daily_columns = {
            "open": (("open_qfq", "open"), "ffill"),
            "close": (("close_qfq", "close"), "ffill"),
            "high": (("high_qfq", "high"), "ffill"),
            "low": (("low_qfq", "low"), "ffill"),
            "volume": ("volume", "zero"),
            "amount": ("amount", "none"),
            "turnover": ("turnover", "none"),
            "market_cap": ("total_mv", "none"),
        }
        if base in daily_columns:
            column, fill = daily_columns[base]
            return self._daily_panel(column, fill=fill), "local_direct", column, "aligned qfq/daily_basic field"

        if base in DERIVED_FIELD_NAMES:
            return self._derived_panel(base, period)

        # Valuation fields are reconstructed from the same PIT primitives.
        valuation: dict[str, tuple[str, str]] = {
            "pb_ratio_lyr": ("market_cap", "equity_parent_company_lyr"),
            "pb_ratio_ttm": ("market_cap", "equity_parent_company_ttm"),
            "pb_ratio_lf": ("market_cap", "equity_parent_company"),
            "book_to_market_ratio_lyr": ("equity_parent_company_lyr", "market_cap"),
            "book_to_market_ratio_ttm": ("equity_parent_company_ttm", "market_cap"),
            "book_to_market_ratio_lf": ("equity_parent_company", "market_cap"),
            "ps_ratio_lyr": ("market_cap", "revenue_lyr"),
            "ps_ratio_ttm": ("market_cap", "revenue_ttm"),
            "sp_ratio_lyr": ("revenue_lyr", "market_cap"),
            "sp_ratio_ttm": ("revenue_ttm", "market_cap"),
            "ev_lyr": ("market_cap", "total_liabilities_lyr"),
            "ev_ttm": ("market_cap", "total_liabilities_ttm"),
            "ev_lf": ("market_cap", "total_liabilities"),
            "ev_no_cash_lyr": ("ev_lyr", "cash_equivalent_lyr"),
            "ev_no_cash_ttm": ("ev_ttm", "cash_equivalent_ttm"),
            "ev_no_cash_lf": ("ev_lf", "cash_equivalent"),
            "ev_to_ebitda_lyr": ("ev_lyr", "ebitda_lyr"),
            "ev_to_ebitda_ttm": ("ev_ttm", "ebitda_ttm"),
            "ev_no_cash_to_ebit_lyr": ("ev_no_cash_lyr", "ebit_lyr"),
            "ev_no_cash_to_ebit_ttm": ("ev_no_cash_ttm", "ebit_ttm"),
        }
        if base == "market_cap_3":
            return self._base_panel("market_cap", "current")[0], "local_direct", "total_mv", "daily_basic total_mv"
        if base in {"a_share_market_val", "a_share_market_val_in_circulation"}:
            source = "market_cap" if base == "a_share_market_val" else "circ_mv"
            source_column = "total_mv" if source == "market_cap" else "circ_mv"
            if source_column not in self._index_frame().columns:
                raise KeyError(f"No local daily_basic source for {source_column}")
            return self._daily_panel(source_column), "local_proxy", source, "daily_basic market-value proxy"
        if base in valuation:
            lhs_name, rhs_name = valuation[base]
            lhs = self._named_array(lhs_name)
            rhs = self._named_array(rhs_name)
            if base in {"ev_lyr", "ev_ttm", "ev_lf"}:
                return lhs + rhs, "local_derived", "", "enterprise value reconstructed from PIT statements"
            if base in {"ev_no_cash_lyr", "ev_no_cash_ttm", "ev_no_cash_lf"}:
                return lhs - rhs, "local_derived", "", "enterprise value less cash reconstructed from PIT statements"
            return _safe_divide(lhs, rhs), "local_derived", "", "valuation reconstructed from PIT statements"
        spec = self._source_spec(base)
        if spec is None:
            raise KeyError(f"No local source mapping for {base}")
        effective_period = period
        if effective_period == "current":
            effective_period = "current"
        panel = self._report_panel(spec.endpoint, spec.column, effective_period)
        return panel, spec.status, f"{spec.endpoint}.{spec.column}", spec.note

    def _named_array(self, name: str) -> np.ndarray:
        normalized = str(name).strip().lower()
        base, period = split_formula_field_name(normalized)
        key = f"{base}:{period}"
        cached = self._array_cache.get(key)
        if cached is not None:
            self._array_cache.move_to_end(key)
            return cached
        array, _, _, _ = self._base_panel(base, period)
        array = np.asarray(array, dtype=np.float32)
        self._array_cache[key] = array
        self._array_cache.move_to_end(key)
        while len(self._array_cache) > self.max_cached_fields:
            self._array_cache.popitem(last=False)
        return array

    def _materialize(self, name: str) -> torch.Tensor:
        normalized = str(name).strip().lower()
        base, period = split_formula_field_name(normalized)
        key = f"{base}:{period}"
        cached = self._panel_cache.get(key)
        if cached is not None:
            self._panel_cache.move_to_end(key)
            return cached
        array = self._named_array(normalized)
        full = np.full((self._full_length, self._n_stocks), np.nan, dtype=np.float32)
        full[self._offset : self._offset + len(self._real_dates)] = array
        tensor = torch.tensor(full, dtype=torch.float32, device=self.data.data.device)
        self._panel_cache[key] = tensor
        self._panel_cache.move_to_end(key)
        while len(self._panel_cache) > self.max_cached_fields:
            self._panel_cache.popitem(last=False)
        return tensor

    def evaluate(self, name: str, period: slice = slice(0, 1)) -> torch.Tensor:
        start = 0 if period.start is None else int(period.start)
        stop = 1 if period.stop is None else int(period.stop)
        if stop <= start:
            raise IndexError(f"Invalid expression period: {period}")
        start_index = start + int(self.data.max_backtrack_days)
        stop_index = stop + int(self.data.max_backtrack_days) + int(self.data.n_days) - 1
        if start_index < 0 or stop_index > self._full_length:
            raise IndexError(f"PandaAI field period is outside local data: {period}")
        return self._materialize(name)[start_index:stop_index]

    def status(self, name: str) -> dict[str, Any]:
        normalized = name.lower()
        cached = self._status_cache.get(normalized)
        if cached is not None:
            return dict(cached)
        base, period = split_formula_field_name(normalized)
        status = "unavailable"
        source = ""
        note = ""
        if base in {"open", "close", "high", "low", "volume", "amount", "turnover", "market_cap"}:
            source_candidates = {
                "open": ("open_qfq", "open"),
                "close": ("close_qfq", "close"),
                "high": ("high_qfq", "high"),
                "low": ("low_qfq", "low"),
                "volume": "volume",
                "amount": "amount",
                "turnover": "turnover",
                "market_cap": "total_mv",
            }[base]
            candidates = (source_candidates,) if isinstance(source_candidates, str) else source_candidates
            source = next((item for item in candidates if item in self._index_frame().columns), "")
            if source:
                status, note = "local_direct", "aligned qfq/daily_basic field"
        elif base in VALUATION_FIELDS or base in DERIVED_FIELD_NAMES:
            try:
                status, source, note = self._computed_status(base, period)
            except (KeyError, FileNotFoundError):
                note = "derived-field inputs are not all present in the local cache"
        else:
            try:
                spec = self._source_spec(base)
            except FileNotFoundError:
                spec = None
            if spec is not None and self._source_available(spec, period):
                status, source, note = spec.status, f"{spec.endpoint}.{spec.column}", spec.note
            else:
                note = "source column is absent from the current cache or has no validated mapping"
        result = {
            "field": normalized,
            "base_field": base,
            "period": period,
            "label": PLATFORM_FIELD_LABELS.get(base, ""),
            "status": status,
            "source": source,
            "note": note,
        }
        self._status_cache[normalized] = result
        return dict(result)

    def all_statuses(self) -> list[dict[str, Any]]:
        return [self.status(name) for name in PLATFORM_FIELD_NAMES]

    def all_formula_statuses(self) -> list[dict[str, Any]]:
        return [
            self.status(name)
            for name in sorted(formula_field_name_set(include_period_variants=True))
        ]

    def active_search_fields(self, include_period_variants: bool = True) -> list[str]:
        names: set[str] = set()
        candidates = (
            formula_field_name_set(include_period_variants=include_period_variants)
            if include_period_variants
            else formula_field_name_set(include_period_variants=False)
        )
        for name in candidates:
            if self.status(name)["status"] != "unavailable":
                names.add(name)
        return sorted(names)

    def summary(self) -> dict[str, Any]:
        statuses = self.all_statuses()
        counts: dict[str, int] = {}
        for item in statuses:
            counts[item["status"]] = counts.get(item["status"], 0) + 1
        return {
            "reference": str(DEFAULT_REFERENCE),
            "platform_fields": len(PLATFORM_FIELD_NAMES),
            "status_counts": counts,
            "active_search_fields": len(self.active_search_fields()),
            "formula_names": len(formula_field_name_set()),
            "max_cached_fields": self.max_cached_fields,
        }

    def coverage_report(self) -> dict[str, Any]:
        base_statuses = self.all_statuses()
        statuses = self.all_formula_statuses()
        counts: dict[str, int] = {}
        for item in statuses:
            status = str(item["status"])
            counts[status] = counts.get(status, 0) + 1
        return {
            "platform_base_fields": len(PLATFORM_FIELD_NAMES),
            "formula_names": len(statuses),
            "status_counts": counts,
            "base_status_counts": {
                status: sum(item["status"] == status for item in base_statuses)
                for status in sorted({item["status"] for item in base_statuses})
            },
            "base_fields": base_statuses,
            "active_search_fields": self.active_search_fields(),
            "fields": statuses,
        }

    def get_named_feature(self, name: str, period: slice = slice(0, 1)) -> torch.Tensor:
        status = self.status(name)
        if status["status"] == "unavailable":
            raise KeyError(
                f"PandaAI field {name} is unavailable in the local cache: {status['note']}"
            )
        return self.evaluate(name, period)


__all__ = [
    "EXPECTED_PLATFORM_FIELD_COUNT",
    "PandaAIField",
    "PandaAIFieldSpec",
    "PandaAIFieldStore",
    "PLATFORM_FIELD_SET",
    "PLATFORM_FIELD_NAMES",
    "PLATFORM_FIELD_SPECS",
    "build_pandaai_namespace",
    "formula_field_name_set",
    "load_platform_field_specs",
    "split_formula_field_name",
]
