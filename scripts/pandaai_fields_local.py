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
from functools import lru_cache
from pathlib import Path
import re
from typing import Any, Iterable

import numpy as np
import pandas as pd
import torch

from alphagen.data.expression import Expression, OutOfDataRangeError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REFERENCE = PROJECT_ROOT / "vendor" / "skill-pandaai-factor-online" / "references" / "fields.md"
DEFAULT_CATALOG_ROOT = DEFAULT_REFERENCE.parent
EXPECTED_PLATFORM_FIELD_COUNT = 348

_FIELD_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*(.*?)\s*\|\s*$")
_PERIOD_SUFFIX = re.compile(
    r"^(?P<base>.+)_(?P<period>lyr|ttm|mrq_(?:[1-9]|1[0-2]))$"
)

# The formula-mode catalog is broader than the fields that have already
# appeared in a saved workflow.  Keep that catalog available for discovery so
# an untested but platform-declared field is not silently discarded.  Barra
# fields are deliberately outside the local factor-search universe, and these
# two financial families are excluded after FactorBuild rejected their period
# variants with ``Missing required base factors`` on 2026-09-16.  Re-enable a
# family only after a fresh online formula validation succeeds.
BARRA_FIELD_NAMES = frozenset(
    {
        "book_to_market_ratio",
        "leverage",
        "liquidity",
        "beta",
        "growth",
        "residual_volatility",
        "non_linear_market_cap",
        "profitability",
        "momentum",
    }
)
PLATFORM_UNSUPPORTED_BASE_FIELDS = frozenset(
    {
        "contract_liabilities",
        "net_profit_parent_company",
    }
)


@dataclass(frozen=True)
class PandaAIFieldSpec:
    name: str
    label: str
    category: str


@dataclass(frozen=True)
class PandaAICatalogFieldSpec:
    name: str
    label: str
    category: str
    source_file: str


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


def _expand_catalog_token(token: str) -> list[str]:
    """Expand compact rows such as ``MA3, 5, 10`` into field names."""
    names: list[str] = []
    numeric_prefix = ""
    for raw_name in re.split(r"[,，]", token):
        name = raw_name.strip().lower()
        if not name:
            continue
        if re.fullmatch(r"\d+", name) and numeric_prefix:
            name = f"{numeric_prefix}{name}"
        if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
            continue
        names.append(name)
        prefix_match = re.match(r"^([a-z_]+)\d+$", name)
        numeric_prefix = prefix_match.group(1) if prefix_match else ""
    return names


def load_platform_catalog_specs(
    reference_root: Path = DEFAULT_CATALOG_ROOT,
) -> tuple[PandaAICatalogFieldSpec, ...]:
    """Load the platform's wider backtest-field catalog.

    ``fields.md`` documents the formula-mode base leaves, while the
    ``fields-*.md`` files are the platform-exported backtest catalog.  The
    latter contains compact rows with comma-separated technical fields, so it
    needs a small structured expansion instead of treating each row as one
    name.  Barra is kept in its own explicit exclusion set and is never part
    of the returned candidate universe.
    """
    specs: list[PandaAICatalogFieldSpec] = []
    seen: set[str] = set()
    for path in sorted(reference_root.glob("fields-*.md")):
        if path.name == "fields-barra.md":
            continue
        category = path.stem.removeprefix("fields-")
        for line in path.read_text(encoding="utf-8").splitlines():
            match = _FIELD_ROW.match(line)
            if match is None:
                continue
            token, label = match.groups()
            for name in _expand_catalog_token(token):
                if name in seen or name in BARRA_FIELD_NAMES:
                    continue
                seen.add(name)
                specs.append(PandaAICatalogFieldSpec(name, label, category, path.name))
    if not specs:
        raise RuntimeError(f"No PandaAI backtest catalog fields found under {reference_root}")
    return tuple(specs)


PLATFORM_FIELD_SPECS = load_platform_field_specs()
PLATFORM_FIELD_NAMES = tuple(spec.name for spec in PLATFORM_FIELD_SPECS)
PLATFORM_FIELD_SET = frozenset(PLATFORM_FIELD_NAMES)
PLATFORM_CATALOG_SPECS = load_platform_catalog_specs()
PLATFORM_CATALOG_FIELD_NAMES = tuple(spec.name for spec in PLATFORM_CATALOG_SPECS)
PLATFORM_CATALOG_FIELD_SET = frozenset(PLATFORM_CATALOG_FIELD_NAMES)
PLATFORM_DECLARED_FIELD_NAMES = tuple(
    dict.fromkeys((*PLATFORM_FIELD_NAMES, *PLATFORM_CATALOG_FIELD_NAMES))
)
PLATFORM_FIELD_LABELS = {
    **{spec.name: spec.label for spec in PLATFORM_FIELD_SPECS},
    **{spec.name: spec.label for spec in PLATFORM_CATALOG_SPECS},
}
PLATFORM_FIELD_CATEGORIES = {
    **{spec.name: spec.category for spec in PLATFORM_FIELD_SPECS},
    **{spec.name: spec.category for spec in PLATFORM_CATALOG_SPECS},
}
PLATFORM_FIELD_SOURCE_FILES = {
    **{spec.name: DEFAULT_REFERENCE.name for spec in PLATFORM_FIELD_SPECS},
    **{spec.name: spec.source_file for spec in PLATFORM_CATALOG_SPECS},
}
CATALOG_STATEMENT_CATEGORIES = frozenset(
    {"balance-sheet", "cashflow-statement", "income-statement"}
)
CATALOG_STATEMENT_FIELD_NAMES = frozenset(
    spec.name
    for spec in PLATFORM_CATALOG_SPECS
    if spec.category in CATALOG_STATEMENT_CATEGORIES
)
CATALOG_DAILY_TECHNICAL_FIELD_NAMES = frozenset(
    spec.name
    for spec in PLATFORM_CATALOG_SPECS
    if spec.category in {"ma-indicators", "oscillators", "volume-indicators"}
    or (spec.category == "cal-date" and spec.name.startswith("cal_"))
)
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


def _platform_formula_name_allowed(name: str) -> bool:
    """Return whether a name is eligible for PandaAI formula search."""
    normalized = str(name).strip().lower()
    if normalized in BARRA_FIELD_NAMES:
        return False
    match = _PERIOD_SUFFIX.match(normalized)
    base = match.group("base") if match else normalized
    return base not in PLATFORM_UNSUPPORTED_BASE_FIELDS


@lru_cache(maxsize=8)
def formula_field_name_set(
    *,
    include_period_variants: bool = True,
    include_mrq_variants: bool = True,
) -> frozenset[str]:
    """Return lower-case names accepted by the local PandaAI formula parser.

    The 348 base names come from the checked-in PandaAI reference and the
    additional names come from the platform backtest catalog.  Formula-mode
    statement fields expose fiscal-year, TTM, and most-recent-report
    variants; catalog statement fields expose the documented ``_mrq_n``
    variants.  Valuation names already contain their period in the base name
    and are therefore not expanded again.
    """
    names = set(PLATFORM_FIELD_NAMES).union(PLATFORM_CATALOG_FIELD_NAMES)
    if not include_period_variants:
        return frozenset(name for name in names if _platform_formula_name_allowed(name))
    suffixes = ("lyr", "ttm")
    if include_mrq_variants:
        suffixes += PERIOD_VARIANT_SUFFIXES[2:]
    for base in STATEMENT_FIELD_NAMES:
        names.update(f"{base}_{suffix}" for suffix in suffixes)
    if include_mrq_variants:
        for base in CATALOG_STATEMENT_FIELD_NAMES:
            names.update(f"{base}_mrq_{index}" for index in range(1, 13))
    return frozenset(name for name in names if _platform_formula_name_allowed(name))


def is_platform_formula_field(name: str) -> bool:
    """Return whether a name is in the declared, non-Barra formula universe."""
    normalized = str(name).strip().lower()
    return _platform_formula_name_allowed(normalized) and normalized in formula_field_name_set()


def split_formula_field_name(name: str) -> tuple[str, str]:
    """Split a formula field into its base name and period selector."""
    normalized = str(name).strip().lower()
    match = _PERIOD_SUFFIX.match(normalized)
    # A few valuation reconstructions use source aliases that are not
    # exposed as standalone platform formula fields (for example ``ebitda``).
    # They still need the same PIT/TTM suffix handling internally.
    internal_bases = set(globals().get("_SOURCE_PAIRS", {}))
    if match and (
        match.group("base") in PLATFORM_FIELD_SET
        or match.group("base") in PLATFORM_CATALOG_FIELD_SET
        or match.group("base") in internal_bases
    ):
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
    "ebit": ("income", "ebit"),
    "ebitda": ("income", "ebitda"),
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


# The wider platform catalog uses compact prefixes for statement fields.  A
# large part of the mapping is mechanical (`is_foo` -> income.foo and
# `bs_foo` -> balancesheet.foo); these aliases cover the names where the
# platform label and Tushare column differ.
_CATALOG_SOURCE_ALIASES: dict[str, tuple[str, str]] = {
    # Income statement.
    "is_net_interest_inc": ("income", "int_income"),
    "is_une_prem_reserve": ("income", "une_prem_reser"),
    "is_compensation_payout": ("income", "compens_payout"),
    "is_compensation_payout_refu": ("income", "compens_payout_refu"),
    "is_reserve_insur_liab": ("income", "reser_insur_liab"),
    "is_insur_reserve_refu": ("income", "insur_reser_refu"),
    "is_net_expo_hedging": ("income", "net_expo_hedging_benefits"),
    "is_credit_impair_loss": ("income", "credit_impa_loss"),
    "is_oper_admin_exp": ("income", "admin_exp"),
    "is_insur_comm_exp": ("income", "comm_exp"),
    "is_non_recurring_pnl": ("fina_indicator", "extra_item"),
    "is_net_after_nr": ("fina_indicator", "profit_dedt"),
    "is_n_income_attr_p": ("income", "n_income_attr_p"),
    "is_oth_affecting_tp": ("income", "total_profit"),
    "is_oth_affecting_np": ("income", "n_income"),
    "is_invest_loss_unconf": ("balancesheet", "invest_loss_unconf"),
    "is_forex_stmt_diff": ("balancesheet", "forex_differ"),
    # Balance-sheet names whose compact spelling is not the Tushare column.
    "bs_notes_receive": ("balancesheet", "notes_receiv"),
    "bs_div_receive": ("balancesheet", "div_receiv"),
    "bs_notes_accts_receiv": ("balancesheet", "accounts_receiv_bill"),
    "bs_int_receive": ("balancesheet", "int_receiv"),
    "bs_net_accts_receive": ("balancesheet", "accounts_receiv"),
    "bs_lease_receive": ("balancesheet", "lt_rec"),
    "bs_oth_illiq_fa": ("balancesheet", "oth_illiq_fin_assets"),
    "bs_oth_receiv_int_div": ("balancesheet", "oth_receiv"),
    "bs_inventory": ("balancesheet", "inventories"),
    "bs_consumable_bio_assets": ("balancesheet", "produc_bio_assets"),
    "bs_fa_avail_sale": ("balancesheet", "fa_avail_for_sale"),
    "bs_ncl_due_1y": ("balancesheet", "non_cur_liab_due_1y"),
    "bs_net_lt_eqt_invest": ("balancesheet", "lt_eqt_invest"),
    "bs_accu_depr": ("cashflow", "depr_fa_coga_dpba"),
    "bs_fix_asset_impair": ("income", "assets_impair_loss"),
    "bs_net_fix_assets": ("balancesheet", "fix_assets"),
    "bs_total_fix_assets": ("balancesheet", "fix_assets_total"),
    "bs_fix_assets_disp": ("balancesheet", "fixed_assets_disp"),
    "bs_prod_bio_assets": ("balancesheet", "produc_bio_assets"),
    "bs_oil_gas_assets": ("balancesheet", "oil_and_gas_assets"),
    "bs_invest_as_receive": ("balancesheet", "invest_as_receiv"),
    "bs_reinsur_reserve_receive": ("balancesheet", "reinsur_res_receiv"),
    "bs_sett_reserve": ("balancesheet", "sett_rsrv"),
    "bs_loan_to_oth_bank_fi": ("balancesheet", "loanto_oth_bank_fi"),
    "bs_premium_receive": ("balancesheet", "premium_receiv"),
    "bs_subrogation_receive": ("balancesheet", "oth_receiv"),
    "bs_reinsur_receive": ("balancesheet", "reinsur_receiv"),
    "bs_oth_receive": ("balancesheet", "oth_receiv"),
    "bs_cap_stk": ("balancesheet", "total_share"),
    "bs_pref_shares": ("balancesheet", "oth_eqt_tools_p_shr"),
    "bs_housing_revolving": ("balancesheet", "specific_payables"),
    "bs_defer_tax_liab": ("balancesheet", "defer_tax_liab"),
    "bs_fin_lease_payable": ("balancesheet", "lease_liab"),
    "bs_oth_fees_payable": ("balancesheet", "oth_payable"),
    "bs_oth_payable_int_div": ("balancesheet", "oth_payable"),
    "bs_perpetual_bond": ("balancesheet", "bond_payable"),
    "bs_lt_payroll_payable": ("balancesheet", "lt_payroll_payable"),
    "bs_depos_oth_bfi": ("balancesheet", "depos_oth_bfi"),
    "bs_total_hldr_eqy_exc_min_int": ("balancesheet", "total_hldr_eqy_exc_min_int"),
    "bs_total_hldr_eqy_inc_min_int": ("balancesheet", "total_hldr_eqy_inc_min_int"),
    "bs_ordin_risk_reserve": ("balancesheet", "ordin_risk_reser"),
    "bs_trade_risk_allow": ("balancesheet", "ordin_risk_reser"),
    "bs_forex_diff": ("balancesheet", "forex_differ"),
    # Cash-flow catalog names.
    "cfs_cash_received_sales": ("cashflow", "c_fr_sale_sg"),
    "cfs_tax_refund": ("cashflow", "recp_tax_rends"),
    "cfs_net_deposit_inc": ("cashflow", "n_depos_incr_fi"),
    "cfs_net_inc_cb_borr": ("cashflow", "n_incr_loans_cb"),
    "cfs_net_inc_oth_fi": ("cashflow", "n_inc_borr_oth_fi"),
    "cfs_recovery_written_off_loans": ("cashflow", "n_incr_clt_loan_adv"),
    "cfs_cash_received_int_comm": ("cashflow", "ifc_cash_incr"),
    "cfs_net_inc_dispose_fa": ("cashflow", "n_incr_disp_tfa"),
    "cfs_net_inc_repurchase": ("cashflow", "n_cap_incr_repur"),
    "cfs_cash_received_orig_ins": ("cashflow", "prem_fr_orig_contr"),
    "cfs_cash_received_reins": ("cashflow", "n_reinsur_prem"),
    "cfs_net_inc_ph_invest": ("cashflow", "n_incr_insured_dep"),
    "cfs_net_inc_borr_capital": ("cashflow", "n_incr_loans_oth_bank"),
    "cfs_cash_received_proxy_sec": ("cashflow", "net_cash_rece_sec"),
    "cfs_cash_received_uw_sec": ("cashflow", "net_cash_rece_sec"),
    "cfs_cash_oth_operating": ("cashflow", "c_fr_oth_operate_a"),
    "cfs_cash_inflow_operating": ("cashflow", "c_inf_fr_operate_a"),
    "cfs_cash_paid_goods": ("cashflow", "c_paid_goods_s"),
    "cfs_asset_depr_reserve": ("cashflow", "prov_depr_assets"),
    "cfs_fx_effect": ("cashflow", "eff_fx_flu_cash"),
    "cfs_oth_affecting_cash": ("cashflow", "others"),
    "cfs_net_inc_cash_equiv": ("cashflow", "n_incr_cash_cash_equ"),
    "cfs_begin_cash_equiv": ("cashflow", "c_cash_equ_beg_period"),
    "cfs_end_cash_equiv": ("cashflow", "c_cash_equ_end_period"),
    "cfs_cash_paid_employees": ("cashflow", "c_paid_to_for_empl"),
    "cfs_cash_paid_taxes": ("cashflow", "c_paid_for_taxes"),
    "cfs_net_inc_loans_advances": ("cashflow", "n_incr_clt_loan_adv"),
    "cfs_net_inc_depos_cb": ("cashflow", "n_incr_dep_cbob"),
    "cfs_net_inc_lend_capital": ("cashflow", "net_dism_capital_add"),
    "cfs_cash_paid_commissions": ("cashflow", "pay_handling_chrg"),
    "cfs_cash_paid_orig_ins": ("cashflow", "c_pay_claims_orig_inco"),
    "cfs_cash_paid_reins": ("cashflow", "oth_cash_pay_oper_act"),
    "cfs_cash_paid_policy_div": ("cashflow", "pay_comm_insur_plcy"),
    "cfs_net_inc_trad_fa": ("cashflow", "n_incr_disp_tfa"),
    "cfs_net_inc_oper_resale": ("cashflow", "n_cap_incr_repur"),
    "cfs_cash_paid_oth_operating": ("cashflow", "oth_cash_pay_oper_act"),
    "cfs_cash_outflow_operating": ("cashflow", "st_cash_out_act"),
    "cfs_net_cash_operating": ("cashflow", "n_cashflow_act"),
    "cfs_cash_received_dispose_inv": ("cashflow", "c_recp_return_invest"),
    "cfs_cash_received_inv_income": ("cashflow", "c_recp_return_invest"),
    "cfs_cash_received_dispose_asset": ("cashflow", "n_recp_disp_fiolta"),
    "cfs_cash_oth_investing": ("cashflow", "oth_recp_ral_inv_act"),
    "cfs_cash_inflow_investing": ("cashflow", "stot_inflows_inv_act"),
    "cfs_cash_paid_asset": ("cashflow", "c_pay_acq_const_fiolta"),
    "cfs_cash_paid_invest": ("cashflow", "c_paid_invest"),
    "cfs_cash_paid_oth_investing": ("cashflow", "oth_pay_ral_inv_act"),
    "cfs_cash_outflow_investing": ("cashflow", "stot_out_inv_act"),
    "cfs_net_cash_investing": ("cashflow", "n_cashflow_inv_act"),
    "cfs_cash_received_investors": ("cashflow", "c_recp_cap_contrib"),
    "cfs_cash_received_minority": ("cashflow", "incl_cash_rec_saims"),
    "cfs_cash_received_issue_bond": ("cashflow", "proc_issue_bonds"),
    "cfs_cash_received_borr": ("cashflow", "c_recp_borrow"),
    "cfs_cash_received_issue_equity": ("cashflow", "c_recp_cap_contrib"),
    "cfs_net_inc_financing_repurchase": ("cashflow", "n_cap_incr_repur"),
    "cfs_cash_oth_financing": ("cashflow", "oth_cash_recp_ral_fnc_act"),
    "cfs_cash_inflow_financing": ("cashflow", "stot_cash_in_fnc_act"),
    "cfs_cash_paid_debt": ("cashflow", "c_prepay_amt_borr"),
    "cfs_cash_paid_div_interest": ("cashflow", "c_pay_dist_dpcp_int_exp"),
    "cfs_div_paid_minority": ("cashflow", "incl_dvd_profit_paid_sc_ms"),
    "cfs_cash_paid_oth_financing": ("cashflow", "oth_cashpay_ral_fnc_act"),
    "cfs_cash_outflow_financing": ("cashflow", "stot_cashout_fnc_act"),
    "cfs_net_cash_financing": ("cashflow", "n_cash_flows_fnc_act"),
    "cfs_net_cash_dispose_sub": ("cashflow", "n_recp_disp_sobu"),
    "cfs_net_cash_acquire_sub": ("cashflow", "n_disp_subs_oth_biz"),
    "cfs_net_inc_pledge_loans": ("cashflow", "n_incr_pledge_loan"),
    "cfs_net_inc_invest_resale": ("cashflow", "n_cap_incr_repur"),
    "cfs_net_inc_cash_equiv_note": ("cashflow", "n_incr_cash_cash_equ"),
    "cfs_fix_asset_depr": ("cashflow", "depr_fa_coga_dpba"),
    "cfs_defer_exp_amort": ("cashflow", "lt_amort_deferred_exp"),
    "cfs_intan_asset_amort": ("cashflow", "amort_intang_assets"),
}


def _catalog_source_pair(base: str) -> tuple[str, str] | None:
    """Resolve a compact platform statement field to a local source column."""
    explicit = _CATALOG_SOURCE_ALIASES.get(base)
    if explicit is not None:
        return explicit
    if base.startswith("is_"):
        return "income", base[3:]
    if base.startswith("bs_"):
        return "balancesheet", base[3:]
    return None


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


def _safe_divide(lhs: np.ndarray | float, rhs: np.ndarray | float) -> np.ndarray:
    left, right = np.broadcast_arrays(
        np.asarray(lhs, dtype=np.float32), np.asarray(rhs, dtype=np.float32)
    )
    result = np.full(left.shape, np.nan, dtype=np.float32)
    valid = np.isfinite(left) & np.isfinite(right) & (np.abs(right) > 1e-12)
    result[valid] = left[valid] / right[valid]
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

_CATALOG_PERIOD_SUFFIX = re.compile(r"^(?P<stem>.+)_(?P<period>lyr|ttm|lf)$")

# These are the names of the corresponding Tushare `fina_indicator` columns.
# The platform catalog exposes both lyr and ttm variants; lyr uses the latest
# annual PIT report and ttm uses the latest available indicator snapshot.  The
# latter is intentionally reported as a proxy because Tushare's indicator
# publication cadence is not byte-identical to PandaAI's internal series.
_CATALOG_INDICATOR_ALIASES: dict[str, str] = {
    # operating-derived
    "oper_diluted_eps": "dt_eps",
    "oper_adj_eps": "eps",
    "oper_adj_diluted_eps": "dt_eps",
    "oper_revenue_per_share": "total_revenue_ps",
    "oper_oper_rev_per_share": "revenue_ps",
    "oper_ebit": "ebit",
    "oper_ebitda": "ebitda",
    "oper_ebit_per_share": "ebit_ps",
    "oper_roe": "roe",
    "oper_roe_diluted": "roe_dt",
    "oper_roe_adj": "roe_yearly",
    "oper_roe_diluted_adj": "roe_dt",
    "oper_roa": "roa",
    "oper_roa_net": "npta",
    "oper_roic": "roic",
    "oper_net_margin": "netprofit_margin",
    "oper_gross_margin": "grossprofit_margin",
    "oper_cost_to_sales": "cogs_of_sales",
    "oper_net_profit_to_rev": "netprofit_margin",
    "oper_oper_profit_to_rev": "op_of_gr",
    "oper_ebit_to_rev": "ebit_of_gr",
    "oper_exp_to_rev": "expense_of_sales",
    "oper_oper_profit_to_tp": "opincome_of_ebt",
    "oper_inv_profit_to_tp": "investincome_of_ebt",
    "oper_non_oper_to_tp": "n_op_profit_of_ebt",
    "oper_tax_to_tp": "tax_to_ebt",
    "oper_adj_profit_ratio": "dtprofit_to_profit",
    "oper_ebitda_to_debt": "ebitda_to_debt",
    "oper_ar_turnover": "ar_turn",
    "oper_ar_turnover_days": "arturn_days",
    "oper_inv_turnover": "inv_turn",
    "oper_cur_asset_turnover": "ca_turn",
    "oper_fix_asset_turnover": "fa_turn",
    "oper_total_asset_turnover": "assets_turn",
    "oper_du_net_margin": "netprofit_margin",
    "oper_du_roe": "roe",
    "oper_du_ebit_to_rev": "op_of_gr",
    "oper_main_profit": "op_income",
    "oper_int_coverage": "ebit_to_interest",
    "oper_oper_cycle": "turn_days",
    # financial-derived
    "fin_non_int_cur_liab": "current_exint",
    "fin_non_int_ncl": "noncurrent_exint",
    "fin_int_debt": "interestdebt",
    "fin_cap_reserve_per_share": "capital_rese_ps",
    "fin_earned_reserve_per_share": "surplus_rese_ps",
    "fin_undistr_profit_per_share": "undist_profit_ps",
    "fin_retained_earn": "retained_earnings",
    "fin_retained_earn_per_share": "retainedps",
    "fin_debt_to_asset": "debt_to_assets",
    "fin_equity_mult": "assets_to_eqt",
    "fin_nca_ratio": "nca_to_assets",
    "fin_invested_cap": "invest_capital",
    "fin_int_debt_to_cap": "int_to_talcap",
    "fin_cur_debt_ratio": "currentdebt_to_debt",
    "fin_ncl_ratio": "longdeb_to_debt",
    "fin_current_ratio": "current_ratio",
    "fin_quick_ratio": "quick_ratio",
    "fin_super_quick_ratio": "cash_ratio",
    "fin_debt_to_equity": "debt_to_eqt",
    "fin_equity_to_debt": "eqt_to_debt",
    "fin_equity_to_int_debt": "eqt_to_interestdebt",
    "fin_net_debt": "netdebt",
    "fin_working_cap": "working_capital",
    "fin_net_working_cap": "networking_capital",
    "fin_lt_debt_to_wc": "longdebt_to_workingcapital",
    "fin_bps": "bps",
    "fin_du_equity_mult": "dp_assets_to_eqt",
    "fin_book_leverage": "assets_to_eqt",
    "fin_equity_ratio": "eqt_to_debt",
    # growth-derived
    "gr_revenue": "or_yoy",
    "gr_roe": "roe_yoy",
    "gr_bps": "bps_yoy",
    "gr_oper_profit": "op_yoy",
    "gr_net_profit": "netprofit_yoy",
    "gr_total_profit": "ebt_yoy",
    "gr_oper_rev": "or_yoy",
    "gr_net_asset": "eqt_yoy",
    "gr_total_asset": "assets_yoy",
    "gr_np_parent": "netprofit_yoy",
    "gr_ocf": "ocf_yoy",
    # cash-flow-derived
    "cfd_flow_per_share": "cfps",
    "cfd_ocf_per_share": "ocfps",
    "cfd_fcff": "fcff",
    "cfd_fcfe": "fcfe",
    "cfd_fcff_per_share": "fcff_ps",
    "cfd_fcfe_per_share": "fcfe_ps",
    "cfd_ocf_to_debt": "ocf_to_debt",
    "cfd_ocf_to_int_debt": "ocf_to_interestdebt",
    "cfd_ocf_to_net_debt": "ocf_to_netdebt",
    "cfd_depr_amort": "daa",
}

_CATALOG_RATIO_TARGETS: dict[str, str] = {
    "ratio_pb_lyr": "pb_ratio_lyr",
    "ratio_pb_ttm": "pb_ratio_ttm",
    "ratio_pb_lf": "pb_ratio_lf",
    "ratio_bm_lyr": "book_to_market_ratio_lyr",
    "ratio_bm_ttm": "book_to_market_ratio_ttm",
    "ratio_bm_lf": "book_to_market_ratio_lf",
    "ratio_ps_lyr": "ps_ratio_lyr",
    "ratio_ps_ttm": "ps_ratio_ttm",
    "ratio_sp_lyr": "sp_ratio_lyr",
    "ratio_sp_ttm": "sp_ratio_ttm",
    "ratio_ev_lyr": "ev_lyr",
    "ratio_ev_ttm": "ev_ttm",
    "ratio_ev_lf": "ev_lf",
    "ratio_ev_no_cash_lyr": "ev_no_cash_lyr",
    "ratio_ev_no_cash_ttm": "ev_no_cash_ttm",
    "ratio_ev_no_cash_lf": "ev_no_cash_lf",
    "ratio_ev_ebitda_lyr": "ev_to_ebitda_lyr",
    "ratio_ev_ebitda_ttm": "ev_to_ebitda_ttm",
    "ratio_ev_no_cash_ebit_lyr": "ev_no_cash_to_ebit_lyr",
    "ratio_ev_no_cash_ebit_ttm": "ev_no_cash_to_ebit_ttm",
    "ratio_div_yield_ttm": "dividend_yield_ttm",
    "ratio_peg_lyr": "peg_ratio_lyr",
    "ratio_peg_ttm": "peg_ratio_ttm",
    "ratio_market_cap_total": "market_cap",
    "ratio_market_cap_float": "a_share_market_val_in_circulation",
    "ratio_a_share_mv": "a_share_market_val",
    "ratio_a_share_mv_float": "a_share_market_val_in_circulation",
}


def _period_suffix(period: str) -> str:
    return "" if period == "current" else f"_{period}"


def _catalog_stem_period(name: str) -> tuple[str, str]:
    match = _CATALOG_PERIOD_SUFFIX.match(str(name).strip().lower())
    if match is None:
        return str(name).strip().lower(), "current"
    return match.group("stem"), match.group("period")


def _shift_panel(values: np.ndarray, periods: int = 1) -> np.ndarray:
    result = np.full_like(values, np.nan, dtype=np.float32)
    if periods == 0:
        return np.asarray(values, dtype=np.float32).copy()
    if periods > 0:
        if periods < len(values):
            result[periods:] = values[:-periods]
    else:
        lead = -periods
        if lead < len(values):
            result[:-lead] = values[lead:]
    return result


def _rolling_panel(values: np.ndarray, window: int, method: str) -> np.ndarray:
    frame = pd.DataFrame(np.asarray(values, dtype=np.float32))
    result = getattr(frame.rolling(window=window, min_periods=window), method)()
    return result.to_numpy(dtype=np.float32, copy=False)


def _rolling_corr_panel(left: np.ndarray, right: np.ndarray, window: int) -> np.ndarray:
    left_mean = _rolling_panel(left, window, "mean")
    right_mean = _rolling_panel(right, window, "mean")
    left_sq_mean = _rolling_panel(left * left, window, "mean")
    right_sq_mean = _rolling_panel(right * right, window, "mean")
    cross_mean = _rolling_panel(left * right, window, "mean")
    covariance = cross_mean - left_mean * right_mean
    left_std = np.maximum(left_sq_mean - left_mean * left_mean, 0.0) ** 0.5
    right_std = np.maximum(right_sq_mean - right_mean * right_mean, 0.0) ** 0.5
    return _safe_divide(covariance, left_std * right_std)


def _rolling_position(values: np.ndarray, window: int, *, maximum: bool) -> np.ndarray:
    result = np.full_like(values, np.nan, dtype=np.float32)
    for end in range(window - 1, len(values)):
        block = values[end - window + 1 : end + 1]
        for column in range(values.shape[1]):
            series = block[:, column]
            valid = np.isfinite(series)
            if not valid.all():
                continue
            result[end, column] = float(
                np.argmax(series) if maximum else np.argmin(series)
            )
    return result


def _rolling_distance(
    left: np.ndarray,
    right: np.ndarray,
    window: int,
) -> np.ndarray:
    left_position = _rolling_position(left, window, maximum=True)
    right_position = _rolling_position(right, window, maximum=False)
    return np.abs(left_position - right_position)


def _rolling_weighted_std(
    values: np.ndarray,
    weights: np.ndarray,
    window: int,
) -> np.ndarray:
    weight_sum = _rolling_panel(weights, window, "sum")
    weighted_mean = _safe_divide(
        _rolling_panel(values * weights, window, "sum"), weight_sum
    )
    second_moment = _safe_divide(
        _rolling_panel(values * values * weights, window, "sum"), weight_sum
    )
    return np.maximum(second_moment - weighted_mean * weighted_mean, 0.0) ** 0.5


def _rolling_slope(values: np.ndarray, window: int) -> np.ndarray:
    result = np.full_like(values, np.nan, dtype=np.float32)
    x = np.arange(window, dtype=np.float32)
    x_centered = x - x.mean()
    denominator = float(np.sum(x_centered * x_centered))
    for end in range(window - 1, len(values)):
        block = values[end - window + 1 : end + 1]
        centered = block - np.nanmean(block, axis=0, keepdims=True)
        valid = np.isfinite(block).all(axis=0)
        result[end, valid] = (
            np.sum(centered[:, valid] * x_centered[:, None], axis=0) / denominator
        )
    return result


def _ema_panel(values: np.ndarray, span: int) -> np.ndarray:
    frame = pd.DataFrame(np.asarray(values, dtype=np.float32))
    return frame.ewm(span=span, adjust=False, min_periods=span).mean().to_numpy(
        dtype=np.float32, copy=False
    )


def _wma_panel(values: np.ndarray, window: int) -> np.ndarray:
    weights = np.arange(1, window + 1, dtype=np.float32)
    denominator = float(weights.sum())
    result = np.full_like(values, np.nan, dtype=np.float32)
    for end in range(window - 1, len(values)):
        block = values[end - window + 1 : end + 1]
        valid = np.isfinite(block).all(axis=0)
        result[end, valid] = (
            np.sum(block[:, valid] * weights[:, None], axis=0) / denominator
        )
    return result


def _sma_cn_panel(values: np.ndarray, window: int, weight: int = 1) -> np.ndarray:
    result = np.full_like(values, np.nan, dtype=np.float32)
    alpha = float(weight) / float(window)
    for row in range(len(values)):
        current = values[row]
        valid = np.isfinite(current)
        if not valid.any():
            continue
        if row == 0:
            result[row, valid] = current[valid]
            continue
        previous = result[row - 1]
        result[row, valid] = np.where(
            np.isfinite(previous[valid]),
            alpha * current[valid] + (1.0 - alpha) * previous[valid],
            current[valid],
        )
    result[: max(window - 1, 0)] = np.nan
    return result


def _rolling_mdd(values: np.ndarray, window: int) -> np.ndarray:
    result = np.full_like(values, np.nan, dtype=np.float32)
    for end in range(window - 1, len(values)):
        block = values[end - window + 1 : end + 1]
        for column in range(values.shape[1]):
            series = block[:, column]
            if not np.isfinite(series).all():
                continue
            running_max = np.maximum.accumulate(series)
            result[end, column] = np.min(series / running_max - 1.0)
    return result


def _cumulative_obv(close: np.ndarray, volume: np.ndarray) -> np.ndarray:
    change = close - _shift_panel(close)
    sign = np.where(change > 0.0, 1.0, np.where(change < 0.0, -1.0, 0.0))
    signed_volume = np.where(np.isfinite(volume), sign * volume, np.nan)
    result = np.full_like(signed_volume, np.nan, dtype=np.float32)
    for column in range(volume.shape[1]):
        series = signed_volume[:, column]
        valid = np.isfinite(series)
        if valid.any():
            result[valid, column] = np.cumsum(series[valid])
    return result


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
        self._technical_cache: dict[str, np.ndarray] = {}
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

    def _catalog_field_available(self, base: str, period: str) -> bool:
        """Check a wider-catalog field without materializing its full panel."""
        if base in CATALOG_DAILY_TECHNICAL_FIELD_NAMES:
            return self._catalog_technical_available(base)
        if base.startswith("ratio_"):
            target = _CATALOG_RATIO_TARGETS.get(base)
            if target is not None:
                target_base, target_period = split_formula_field_name(target)
                return self._field_available(target_base, target_period)
            stem, selected_period = _catalog_stem_period(base)
            if selected_period == "current":
                selected_period = period
            if stem in {"ratio_pe", "ratio_ep"}:
                return (
                    self._daily_available("total_mv")
                    and self._source_present("income", "n_income_attr_p", selected_period)
                )
            if stem in {"ratio_pcf_total", "ratio_pcf_ocf", "ratio_cfp"}:
                return (
                    self._daily_available("total_mv")
                    and self._source_present("cashflow", "n_cashflow_act", selected_period)
                )
            return False
        if base.startswith(("oper_", "fin_", "gr_", "cfd_")):
            stem, selected_period = _catalog_stem_period(base)
            if selected_period == "current":
                selected_period = period
            column = _CATALOG_INDICATOR_ALIASES.get(stem)
            if column is None:
                return False
            return self._source_present("fina_indicator", column, selected_period)
        spec = self._source_spec(base)
        return spec is not None and self._source_available(spec, period)

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
        if base in PLATFORM_CATALOG_FIELD_SET:
            available = self._catalog_field_available(base, period)
            return (
                "local_proxy" if available else "unavailable",
                "aligned qfq OHLCV/daily_basic" if available and base in CATALOG_DAILY_TECHNICAL_FIELD_NAMES
                else "PIT Tushare/catalog-field reconstruction" if available else "",
                "PandaAI daily technical field reconstructed locally; exact platform implementation is not byte-verified"
                if available and base in CATALOG_DAILY_TECHNICAL_FIELD_NAMES
                else "platform catalog field mapped to an aligned Tushare source or derived indicator"
                if available
                else "catalog-field inputs are not all present in the local cache or have no local handler",
            )
        return "unavailable", "", "no local computed-field handler"

    def _source_spec(self, base: str) -> SourceSpec | None:
        pair = _SOURCE_PAIRS.get(base)
        if pair is None:
            pair = _catalog_source_pair(base)
        if pair is None:
            return None
        endpoint, column = pair
        cache = self._ensure_financial_cache()
        source_columns = self._source_columns.get(endpoint, set(cache.get(endpoint, pd.DataFrame()).columns))
        if column not in source_columns:
            return None
        is_catalog_field = base in PLATFORM_CATALOG_FIELD_SET
        status = "local_proxy" if base in PROXY_FIELDS or is_catalog_field else "local_direct"
        note = (
            "platform catalog field mapped to Tushare source; semantic proxy"
            if is_catalog_field
            else "Tushare alias/proxy"
            if status == "local_proxy"
            else "PIT Tushare statement field"
        )
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
        if base in PLATFORM_CATALOG_FIELD_SET:
            return self._catalog_field_available(base, period)
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
            # The direct platform field family is excluded after FactorBuild
            # rejected it, but the underlying Tushare source is still useful
            # for a clearly labelled local PEG proxy.
            earnings = self._report_panel("income", "n_income_attr_p", earnings_period)
            growth = self._indicator_panel("netprofit_yoy", earnings_period)
            pe = _safe_divide(self._named_array("market_cap"), earnings)
            return (
                _safe_divide(pe, growth),
                "local_proxy",
                f"daily_basic.total_mv / income.{earnings_period}.n_income_attr_p / fina_indicator.{earnings_period}.netprofit_yoy",
                "PEG proxy using Tushare net-profit growth percentage; platform denominator is not byte-equivalent",
            )
        raise KeyError(f"No local derived field handler for {base}")

    def _catalog_ratio_panel(self, base: str, period: str) -> tuple[np.ndarray, str, str, str]:
        """Reconstruct the platform valuation names from PIT primitives."""
        target = _CATALOG_RATIO_TARGETS.get(base)
        if target is not None:
            return (
                self._named_array(target),
                "local_proxy",
                f"PIT reconstruction via {target}",
                "platform backtest valuation field mapped to the aligned local valuation primitive",
            )

        stem, selected_period = _catalog_stem_period(base)
        if selected_period == "current":
            selected_period = period
        if stem in {"ratio_pe", "ratio_ep"}:
            earnings_period = selected_period if selected_period in {"lyr", "ttm"} else "current"
            earnings = self._report_panel("income", "n_income_attr_p", earnings_period)
            market_cap = self._named_array("market_cap")
            ep = _safe_divide(earnings, market_cap)
            value = ep if stem == "ratio_ep" else _safe_divide(market_cap, earnings)
            return (
                value,
                "local_proxy",
                f"income.{earnings_period}.n_income_attr_p / daily_basic.total_mv",
                "Tushare PIT earnings valuation proxy; platform field semantics are not byte-equivalent",
            )
        if stem in {"ratio_pcf_total", "ratio_pcf_ocf", "ratio_cfp"}:
            cashflow = self._report_panel("cashflow", "n_cashflow_act", selected_period)
            market_cap = self._named_array("market_cap")
            value = (
                _safe_divide(cashflow, market_cap)
                if stem == "ratio_cfp"
                else _safe_divide(market_cap, cashflow)
            )
            return (
                value,
                "local_proxy",
                f"cashflow.{selected_period}.n_cashflow_act / daily_basic.total_mv",
                "Tushare cash-flow valuation proxy; total/operating cash-flow definitions may differ",
            )
        raise KeyError(f"No local valuation handler for platform catalog field {base}")

    def _catalog_indicator_panel(
        self,
        base: str,
        period: str,
    ) -> tuple[np.ndarray, str, str, str]:
        stem, selected_period = _catalog_stem_period(base)
        if selected_period == "current":
            selected_period = period
        column = _CATALOG_INDICATOR_ALIASES.get(stem)
        if column is None:
            raise KeyError(f"No local indicator mapping for platform catalog field {base}")
        source_period = "lyr" if selected_period == "lyr" else "current"
        return (
            self._indicator_panel(column, source_period),
            "local_proxy",
            f"fina_indicator.{column}",
            "platform derived field mapped to Tushare fina_indicator; period semantics are explicitly proxy",
        )

    def _catalog_technical_available(self, base: str) -> bool:
        if base not in CATALOG_DAILY_TECHNICAL_FIELD_NAMES:
            return False
        has_ohlcv = all(
            self._daily_available(columns)
            for columns in (
                ("open_qfq", "open"),
                ("close_qfq", "close"),
                ("high_qfq", "high"),
                ("low_qfq", "low"),
                "volume",
            )
        )
        if not has_ohlcv:
            return False
        turnover_required = (
            (base.startswith("vol") and not base.startswith("volt"))
            or base.startswith("davol")
            or base in {
                "cal_5d_turnover_sum",
                "cal_10d_avg_turnover",
                "cal_10d_120d_turnover_ratio",
                "cal_120d_avg_turnover",
                "cal_20d_avg_turnover",
                "cal_20d_120d_turnover_ratio",
                "cyf",
                "sws",
                "mcst",
            }
        )
        return not turnover_required or self._daily_available("turnover")

    def _catalog_technical_panel(
        self,
        base: str,
    ) -> tuple[np.ndarray, str, str, str]:
        cached = self._technical_cache.get(base)
        if cached is not None:
            return (
                cached,
                "local_proxy",
                "aligned qfq OHLCV/daily_basic",
                "PandaAI daily technical field reconstructed locally; exact platform implementation is not byte-verified",
            )
        if not self._catalog_technical_available(base):
            raise KeyError(f"No aligned daily input for PandaAI technical field {base}")

        open_ = self._daily_panel(("open_qfq", "open"), fill="ffill")
        close = self._daily_panel(("close_qfq", "close"), fill="ffill")
        high = self._daily_panel(("high_qfq", "high"), fill="ffill")
        low = self._daily_panel(("low_qfq", "low"), fill="ffill")
        volume = self._daily_panel("volume", fill="zero")
        turnover = self._daily_panel("turnover")
        amount = self._daily_panel("amount")
        amount_fallback = volume * (open_ + close) / 2.0
        amount = np.where(np.isfinite(amount) & (amount > 0.0), amount, amount_fallback)
        previous_close = _shift_panel(close)
        returns = _safe_divide(close, previous_close) - 1.0

        source = "aligned qfq OHLCV/daily_basic"
        note = (
            "PandaAI daily technical field reconstructed locally; exact platform implementation "
            "is not byte-verified"
        )

        def finish(value: np.ndarray) -> tuple[np.ndarray, str, str, str]:
            result = np.asarray(value, dtype=np.float32)
            self._technical_cache[base] = result
            return result, "local_proxy", source, note

        if base.startswith("cal_"):
            if base == "cal_daily_rise":
                return finish(_safe_divide(close, open_) - 1.0)
            if base == "cal_vwap":
                return finish(_safe_divide(amount, volume))
            if base == "cal_limit_up":
                return finish(previous_close * 1.10)
            if base == "cal_limit_down":
                return finish(previous_close * 0.90)
            if base.startswith("cal_30d_"):
                window = 30
                prefix = "cal_30d_"
            elif base.startswith("cal_5d_"):
                window = 5
                prefix = "cal_5d_"
            else:
                window = 0
                prefix = ""
            if window:
                close_mean = _rolling_panel(close, window, "mean")
                close_std = _rolling_panel(close, window, "std")
                volume_mean = _rolling_panel(volume, window, "mean")
                volume_change = volume - _shift_panel(volume)
                volume_decrease = np.where(volume_change < 0.0, -volume_change, 0.0)
                abs_volume_change = np.abs(volume_change)
                up = np.where(returns > 0.0, 1.0, 0.0)
                down = np.where(returns < 0.0, 1.0, 0.0)
                if base == f"{prefix}vol_dec_ratio":
                    return finish(
                        _safe_divide(
                            _rolling_panel(volume_decrease, window, "sum"),
                            _rolling_panel(abs_volume_change, window, "sum"),
                        )
                    )
                if base == f"{prefix}avg_vol_ratio":
                    return finish(_safe_divide(volume_mean, volume))
                if base == f"{prefix}max_high_ratio":
                    return finish(_safe_divide(_rolling_panel(high, window, "max"), close))
                if base == f"{prefix}up_down_diff":
                    return finish(
                        _rolling_panel(up, window, "mean")
                        - _rolling_panel(down, window, "mean")
                    )
                if base == f"{prefix}close_std_ratio":
                    return finish(_safe_divide(close_std, close))
                if base == f"{prefix}close_avg_ratio":
                    return finish(_safe_divide(close_mean, close))
                if base == f"{prefix}up_day_ratio":
                    return finish(_rolling_panel(up, window, "mean"))
                if base == f"{prefix}down_day_ratio":
                    return finish(_rolling_panel(down, window, "mean"))
                if base == "cal_30d_price_vol_corr":
                    return finish(_rolling_corr_panel(close, volume, window))
                if base == "cal_30d_ret_vol_corr":
                    return finish(_rolling_corr_panel(returns, volume_change, window))
                if base == f"{prefix}high_low_dist":
                    return finish(_rolling_distance(high, low, window))
                if base == "cal_5d_vol_std_ratio":
                    return finish(_safe_divide(_rolling_panel(volume, window, "std"), volume))
                if base == "cal_5d_vol_wgt_std":
                    return finish(_rolling_weighted_std(close, volume, window))
                if base == "cal_5d_vol_net_chg":
                    return finish(
                        _safe_divide(
                            _rolling_panel(volume_change, window, "sum"),
                            _rolling_panel(abs_volume_change, window, "sum"),
                        )
                    )
                if base == "cal_5d_turnover_sum":
                    return finish(_rolling_panel(turnover, window, "sum"))
                if base == "cal_5d_min_low_ratio":
                    return finish(_safe_divide(_rolling_panel(low, window, "min"), close))
                if base == "cal_5d_return":
                    return finish(_safe_divide(close, _shift_panel(close, window)) - 1.0)
                if base == "cal_5d_min_low_idx":
                    return finish(_rolling_position(low, window, maximum=False))
                if base == "cal_5d_max_high_idx":
                    return finish(_rolling_position(high, window, maximum=True))
            if base == "cal_10d_vol_std":
                return finish(_rolling_panel(volume, 10, "std"))
            if base == "cal_10d_avg_turnover":
                return finish(_rolling_panel(turnover, 10, "mean"))
            if base == "cal_10d_120d_turnover_ratio":
                return finish(
                    _safe_divide(
                        _rolling_panel(turnover, 10, "mean"),
                        _rolling_panel(turnover, 120, "mean"),
                    )
                )
            if base == "cal_120d_avg_turnover":
                return finish(_rolling_panel(turnover, 120, "mean"))
            if base == "cal_12d_vol_ma":
                return finish(_rolling_panel(volume, 12, "mean"))
            if base == "cal_20d_amt_std":
                return finish(_rolling_panel(amount, 20, "std"))
            if base == "cal_20d_amt_ma":
                return finish(_rolling_panel(amount, 20, "mean"))
            if base == "cal_20d_vol_std":
                return finish(_rolling_panel(volume, 20, "std"))
            if base == "cal_20d_avg_turnover":
                return finish(_rolling_panel(turnover, 20, "mean"))
            if base == "cal_20d_120d_turnover_ratio":
                return finish(
                    _safe_divide(
                        _rolling_panel(turnover, 20, "mean"),
                        _rolling_panel(turnover, 120, "mean"),
                    )
                )

        if base in {"macd_diff", "macd_dea", "macd_hist"}:
            diff = _ema_panel(close, 12) - _ema_panel(close, 26)
            dea = _ema_panel(diff, 9)
            return finish({"macd_diff": diff, "macd_dea": dea, "macd_hist": 2.0 * (diff - dea)}[base])
        if base in {"trix", "matrix"}:
            triple = _ema_panel(_ema_panel(_ema_panel(close, 12), 12), 12)
            trix = _safe_divide(triple, _shift_panel(triple)) - 1.0
            return finish(trix if base == "trix" else _rolling_panel(trix, 20, "mean"))
        if base in {"boll", "boll_up", "boll_down"}:
            mean = _rolling_panel(close, 20, "mean")
            band = 2.0 * _rolling_panel(close, 20, "std")
            return finish({"boll": mean, "boll_up": mean + band, "boll_down": mean - band}[base])
        if base in {"asi", "asit"}:
            lc = previous_close
            aa = np.abs(high - lc)
            bb = np.abs(low - lc)
            cc = np.abs(high - _shift_panel(low))
            dd = np.abs(lc - _shift_panel(open_))
            r = np.where(
                (aa >= bb) & (aa >= cc),
                aa + bb / 2.0 + dd / 4.0,
                np.where((bb >= aa) & (bb >= cc), bb + aa / 2.0 + dd / 4.0, cc + dd / 4.0),
            )
            x = close - lc + (close - open_) / 2.0 + lc - _shift_panel(open_)
            si = _safe_divide(16.0 * x, r * np.maximum(aa, bb))
            asi = _rolling_panel(si, 26, "sum")
            return finish(asi if base == "asi" else _rolling_panel(asi, 10, "mean"))
        match = re.fullmatch(r"(ma|ema|hma|lma|vma|amv|vol|davol)(\d+)", base)
        if match:
            kind, text_window = match.groups()
            window = int(text_window)
            if kind == "ma":
                return finish(_rolling_panel(close, window, "mean"))
            if kind == "ema":
                return finish(_ema_panel(close, window))
            if kind == "hma":
                return finish(_rolling_panel(high, window, "mean"))
            if kind == "lma":
                return finish(_rolling_panel(low, window, "mean"))
            if kind == "vma":
                return finish(_rolling_panel((high + open_ + low + close) / 4.0, window, "mean"))
            if kind == "amv":
                weighted_price = volume * (open_ + close) / 2.0
                return finish(
                    _safe_divide(
                        _rolling_panel(weighted_price, window, "sum"),
                        _rolling_panel(volume, window, "sum"),
                    )
                )
            if kind == "vol":
                return finish(_rolling_panel(turnover, window, "mean"))
            if kind == "davol":
                return finish(
                    _safe_divide(
                        _rolling_panel(turnover, window, "mean"),
                        _rolling_panel(turnover, 120, "mean"),
                    )
                )
        if base in {"bbi", "bbiboll_up", "bbiboll_down"}:
            bbi = sum(_rolling_panel(close, window, "mean") for window in (3, 6, 12, 24)) / 4.0
            band = 6.0 * _rolling_panel(bbi, 11, "std")
            return finish({"bbi": bbi, "bbiboll_up": bbi + band, "bbiboll_down": bbi - band}[base])
        if base in {"dpo", "madpo"}:
            dpo = close - _shift_panel(_rolling_panel(close, 20, "mean"), 10)
            return finish(dpo if base == "dpo" else _rolling_panel(dpo, 6, "mean"))
        if base == "mcst":
            vwap = _safe_divide(amount, volume)
            alpha = np.clip(np.nan_to_num(turnover / 100.0, nan=0.01), 0.01, 1.0)
            mcst = np.full_like(vwap, np.nan, dtype=np.float32)
            for row in range(len(vwap)):
                if row == 0:
                    mcst[row] = vwap[row]
                else:
                    mcst[row] = alpha[row] * vwap[row] + (1.0 - alpha[row]) * mcst[row - 1]
            return finish(mcst)

        if base == "obos":
            daily_breadth = np.nansum(np.where(returns > 0.0, 1.0, 0.0), axis=1) - np.nansum(
                np.where(returns < 0.0, 1.0, 0.0), axis=1
            )
            breadth = pd.Series(daily_breadth).rolling(10, min_periods=10).sum().to_numpy(dtype=np.float32)
            return finish(np.repeat(breadth[:, None], self._n_stocks, axis=1))
        if base in {"kdj_k", "kdj_d", "kdj_j"}:
            low_value = _rolling_panel(low, 9, "min")
            high_value = _rolling_panel(high, 9, "max")
            rsv = _safe_divide(close - low_value, high_value - low_value) * 100.0
            k = _ema_panel(rsv, 5)
            d = _ema_panel(k, 5)
            return finish({"kdj_k": k, "kdj_d": d, "kdj_j": 3.0 * k - 2.0 * d}[base])
        if base in {"rsi6", "rsi10"}:
            window = int(base[3:])
            change = close - previous_close
            up = np.maximum(change, 0.0)
            rsi = _safe_divide(
                _rolling_panel(up, window, "mean"),
                _rolling_panel(np.abs(change), window, "mean"),
            ) * 100.0
            return finish(rsi)
        if base == "wr":
            high_value = _rolling_panel(high, 10, "max")
            low_value = _rolling_panel(low, 10, "min")
            return finish(_safe_divide(high_value - close, high_value - low_value) * 100.0)
        if base in {"lwr1", "lwr2"}:
            high_value = _rolling_panel(high, 9, "max")
            low_value = _rolling_panel(low, 9, "min")
            rsv = _safe_divide(high_value - close, high_value - low_value) * 100.0
            lwr1 = _sma_cn_panel(rsv, 3, 1)
            lwr2 = _sma_cn_panel(lwr1, 3, 1)
            return finish(lwr1 if base == "lwr1" else lwr2)
        if base in {"bias5", "bias10", "bias20"}:
            window = int(base[4:])
            mean = _rolling_panel(close, window, "mean")
            return finish(_safe_divide(close - mean, mean) * 100.0)
        if base in {"bias36", "bias612", "mabias"}:
            bias36 = _rolling_panel(close, 3, "mean") - _rolling_panel(close, 6, "mean")
            bias612 = _rolling_panel(close, 6, "mean") - _rolling_panel(close, 12, "mean")
            return finish(
                bias36
                if base == "bias36"
                else bias612
                if base == "bias612"
                else _rolling_panel(bias36, 6, "mean")
            )
        if base == "accer":
            return finish(_safe_divide(_rolling_slope(close, 8), close))
        if base == "cyf":
            hsl_ema = _ema_panel(turnover, 21)
            return finish(100.0 - _safe_divide(100.0, 1.0 + hsl_ema))
        if base in {"swl", "sws"}:
            swl = (_ema_panel(close, 5) * 7.0 + _ema_panel(close, 10) * 3.0) / 10.0
            sws = _ema_panel(close, 12)
            return finish(swl if base == "swl" else sws)
        if base in {"adtm", "maadtm"}:
            previous_open = _shift_panel(open_)
            dtm = np.where(
                open_ <= previous_open,
                0.0,
                np.maximum(high - open_, open_ - previous_open),
            )
            dbm = np.where(
                open_ >= previous_open,
                0.0,
                np.maximum(open_ - low, open_ - previous_open),
            )
            stm = _rolling_panel(dtm, 23, "sum")
            sbm = _rolling_panel(dbm, 23, "sum")
            adtm = np.where(
                stm > sbm,
                _safe_divide(stm - sbm, stm),
                np.where(stm == sbm, 0.0, _safe_divide(stm - sbm, sbm)),
            )
            return finish(adtm if base == "adtm" else _rolling_panel(adtm, 8, "mean"))
        if base in {"tr", "atr"}:
            true_range = np.maximum.reduce(
                [high - low, np.abs(high - previous_close), np.abs(low - previous_close)]
            )
            tr = _rolling_panel(true_range, 9, "sum")
            return finish(tr if base == "tr" else _rolling_panel(tr, 14, "mean"))
        if base in {"dkx", "madkx"}:
            mid = (3.0 * close + low + open_ + high) / 6.0
            dkx = np.zeros_like(mid, dtype=np.float32)
            valid = np.ones_like(mid, dtype=bool)
            for lag, weight in enumerate(range(20, 0, -1)):
                shifted = _shift_panel(mid, lag)
                valid &= np.isfinite(shifted)
                dkx += weight * np.nan_to_num(shifted, nan=0.0)
            dkx /= 210.0
            dkx[~valid] = np.nan
            return finish(dkx if base == "dkx" else _rolling_panel(dkx, 10, "mean"))
        if base in {"tapi", "matapi"}:
            tapi = _safe_divide(amount, close)
            return finish(tapi if base == "tapi" else _rolling_panel(tapi, 6, "mean"))
        if base == "osc":
            return finish(100.0 * (close - _rolling_panel(close, 10, "mean")))
        if base == "cci":
            typ = (high + low + close) / 3.0
            mean = _rolling_panel(typ, 14, "mean")
            mean_deviation = _rolling_panel(np.abs(typ - mean), 14, "mean")
            return finish(_safe_divide(typ - mean, 0.015 * mean_deviation))
        if base == "roc":
            return finish(_safe_divide(close - _shift_panel(close, 12), _shift_panel(close, 12)) * 100.0)
        if base == "mfi":
            typ = (high + low + close) / 3.0
            typ_change = typ - _shift_panel(typ)
            positive = np.where(typ_change > 0.0, typ * volume, 0.0)
            negative = np.where(typ_change < 0.0, typ * volume, 0.0)
            ratio = _safe_divide(_rolling_panel(positive, 14, "sum"), _rolling_panel(negative, 14, "sum"))
            return finish(100.0 - _safe_divide(100.0, 1.0 + ratio))
        if base in {"mtm", "mamtm"}:
            mtm = close - _shift_panel(close, 14)
            return finish(mtm if base == "mtm" else _rolling_panel(mtm, 6, "mean"))
        if base in {"marsi6", "marsi10"}:
            window = int(base[5:])
            change = close - previous_close
            rsi = _safe_divide(
                _rolling_panel(np.maximum(change, 0.0), window, "mean"),
                _rolling_panel(np.abs(change), window, "mean"),
            ) * 100.0
            return finish(_rolling_panel(rsi, window, "mean"))
        if base in {"skd_k", "skd_d"}:
            low_value = _rolling_panel(low, 9, "min")
            high_value = _rolling_panel(high, 9, "max")
            rsv = _safe_divide(close - low_value, high_value - low_value) * 100.0
            skd_k = _ema_panel(_ema_panel(rsv, 3), 3)
            return finish(skd_k if base == "skd_k" else _rolling_panel(skd_k, 3, "mean"))
        if base in {"udl", "maudl"}:
            udl = sum(_rolling_panel(close, window, "mean") for window in (3, 5, 10, 20)) / 4.0
            return finish(udl if base == "udl" else _rolling_panel(udl, 6, "mean"))
        if base in {"di1", "di2", "adx", "adxr"}:
            hd = high - _shift_panel(high)
            ld = _shift_panel(low) - low
            dmp = _rolling_panel(np.where((hd > 0.0) & (hd > ld), hd, 0.0), 14, "sum")
            dmm = _rolling_panel(np.where((ld > 0.0) & (ld > hd), ld, 0.0), 14, "sum")
            true_range = np.maximum.reduce(
                [high - low, np.abs(high - previous_close), np.abs(low - previous_close)]
            )
            tr_sum = _rolling_panel(true_range, 14, "sum")
            di1 = _safe_divide(dmp * 100.0, tr_sum)
            di2 = _safe_divide(dmm * 100.0, tr_sum)
            adx = _rolling_panel(_safe_divide(np.abs(di2 - di1), di1 + di2) * 100.0, 6, "mean")
            adxr = (adx + _shift_panel(adx, 6)) / 2.0
            return finish({"di1": di1, "di2": di2, "adx": adx, "adxr": adxr}[base])

        if base in {"ar", "br", "vr", "mavr", "cr", "macr1", "macr2", "macr3", "macr4"}:
            if base in {"ar", "br"}:
                ar = _safe_divide(_rolling_panel(high - open_, 26, "sum"), _rolling_panel(open_ - low, 26, "sum")) * 100.0
                br = _safe_divide(
                    _rolling_panel(np.maximum(high - previous_close, 0.0), 26, "sum"),
                    _rolling_panel(np.maximum(previous_close - low, 0.0), 26, "sum"),
                ) * 100.0
                return finish(ar if base == "ar" else br)
            if base in {"vr", "mavr"}:
                up_volume = np.where(close > previous_close, volume, 0.0)
                down_volume = np.where(close <= previous_close, volume, 0.0)
                vr = _safe_divide(_rolling_panel(up_volume, 26, "sum"), _rolling_panel(down_volume, 26, "sum")) * 100.0
                return finish(vr if base == "vr" else _rolling_panel(vr, 6, "mean"))
            mid = _shift_panel(high + low) / 2.0
            cr = _safe_divide(
                _rolling_panel(np.maximum(high - mid, 0.0), 26, "sum"),
                _rolling_panel(np.maximum(mid - low, 0.0), 26, "sum"),
            ) * 100.0
            if base == "cr":
                return finish(cr)
            window = {"macr1": 10, "macr2": 20, "macr3": 40, "macr4": 62}[base]
            return finish(_shift_panel(_rolling_panel(cr, window, "mean"), max(1, int(1 + window / 2.5))))
        if base in {"mass", "mamass"}:
            spread = high - low
            ma9 = _rolling_panel(spread, 9, "mean")
            ratio = _safe_divide(ma9, _rolling_panel(ma9, 9, "mean"))
            mass = _rolling_panel(ratio, 25, "sum")
            return finish(mass if base == "mass" else _rolling_panel(mass, 6, "mean"))
        if base == "sy":
            return finish(_rolling_panel(np.where(returns > 0.0, 100.0, 0.0), 9, "mean"))
        if base == "pcnt":
            return finish(_safe_divide(close - previous_close, close) * 100.0)
        if base in {"cyr", "macyr"}:
            dive = _safe_divide(0.01 * _ema_panel(amount, 13), _ema_panel(volume, 13))
            cyr = _safe_divide(dive, _shift_panel(dive)) - 1.0
            return finish(cyr if base == "cyr" else _rolling_panel(cyr, 5, "mean"))
        match = re.fullmatch(r"amp(1|3|5|10|20|60)", base)
        if match:
            window = int(match.group(1))
            return finish(
                _safe_divide(
                    _rolling_panel(high, window, "max") - _rolling_panel(low, window, "min"),
                    _shift_panel(close, window),
                )
            )
        match = re.fullmatch(r"wma(3|5|10|20|60|120|250)", base)
        if match:
            return finish(_wma_panel(close, int(match.group(1))))
        if base in {"volt20", "volt60"}:
            return finish(_rolling_panel(close, int(base[4:]), "std"))
        if base in {"mdd20", "mdd60"}:
            return finish(_rolling_mdd(close, int(base[3:])))
        if base in {"aroon_up", "aroon_down"}:
            window = 14
            high_position = _rolling_position(high, window, maximum=True)
            low_position = _rolling_position(low, window, maximum=False)
            up = (high_position + 1.0) * 100.0 / window
            down = (low_position + 1.0) * 100.0 / window
            return finish(up if base == "aroon_up" else down)
        if base == "qtyr_5_20":
            return finish(_safe_divide(_rolling_panel(volume, 5, "mean"), _rolling_panel(volume, 20, "mean")))
        if base == "obv":
            return finish(_cumulative_obv(close, volume))
        raise KeyError(f"No local technical handler for PandaAI field {base}")

    def _catalog_panel(self, base: str, period: str) -> tuple[np.ndarray, str, str, str]:
        """Resolve fields that exist in the wider platform catalog."""
        if base in CATALOG_DAILY_TECHNICAL_FIELD_NAMES:
            return self._catalog_technical_panel(base)
        if base.startswith("ratio_"):
            return self._catalog_ratio_panel(base, period)
        if base.startswith(("oper_", "fin_", "gr_", "cfd_")):
            return self._catalog_indicator_panel(base, period)
        spec = self._source_spec(base)
        if spec is not None:
            return (
                self._report_panel(spec.endpoint, spec.column, period),
                spec.status,
                f"{spec.endpoint}.{spec.column}",
                spec.note,
            )
        raise KeyError(f"No local handler for platform catalog field {base}")

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
        if base in PLATFORM_CATALOG_FIELD_SET:
            return self._catalog_panel(base, period)
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
        if period.step not in (None, 1):
            raise ValueError(f"Named-field evaluation only supports unit steps: {period}")
        start = 0 if period.start is None else int(period.start)
        stop = 1 if period.stop is None else int(period.stop)
        if stop <= start:
            raise IndexError(f"Invalid expression period: {period}")
        # Match AlphaPROBE's built-in Feature boundary contract.  Rolling
        # expressions can request more history than the configured panel; the
        # caller should treat that candidate as out of range and continue.
        if (
            start < -int(self.data.max_backtrack_days)
            or stop - 1 > int(self.data.max_future_days)
        ):
            raise OutOfDataRangeError()
        start_index = start + int(self.data.max_backtrack_days)
        stop_index = stop + int(self.data.max_backtrack_days) + int(self.data.n_days) - 1
        if start_index < 0 or stop_index > self._full_length:
            raise OutOfDataRangeError()
        return self._materialize(name)[start_index:stop_index]

    def status(self, name: str) -> dict[str, Any]:
        normalized = str(name).strip().lower()
        cached = self._status_cache.get(normalized)
        if cached is not None:
            return dict(cached)
        base, period = split_formula_field_name(normalized)
        status = "unavailable"
        source = ""
        note = ""
        if not is_platform_formula_field(normalized):
            if normalized in BARRA_FIELD_NAMES:
                note = "Barra field excluded from the factor-search universe"
            elif base in PLATFORM_UNSUPPORTED_BASE_FIELDS:
                note = "FactorBuild rejected this field family: Missing required base factors"
            else:
                note = "field is not in the PandaAI formula-mode catalog"
        elif base in {"open", "close", "high", "low", "volume", "amount", "turnover", "market_cap"}:
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
        elif (
            base in VALUATION_FIELDS
            or base in DERIVED_FIELD_NAMES
            or base in PLATFORM_CATALOG_FIELD_SET
        ):
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
            "category": PLATFORM_FIELD_CATEGORIES.get(base, ""),
            "source_file": PLATFORM_FIELD_SOURCE_FILES.get(base, ""),
            "status": status,
            "source": source,
            "note": note,
        }
        self._status_cache[normalized] = result
        return dict(result)

    def all_statuses(self) -> list[dict[str, Any]]:
        return [self.status(name) for name in PLATFORM_DECLARED_FIELD_NAMES]

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
            "platform_formula_fields": len(PLATFORM_FIELD_NAMES),
            "platform_catalog_fields": len(PLATFORM_CATALOG_FIELD_NAMES),
            "catalog_statement_fields": len(CATALOG_STATEMENT_FIELD_NAMES),
            "catalog_daily_technical_fields": len(CATALOG_DAILY_TECHNICAL_FIELD_NAMES),
            "platform_declared_fields": len(PLATFORM_DECLARED_FIELD_NAMES),
            "barra_fields_excluded": sorted(BARRA_FIELD_NAMES),
            "unsupported_base_fields": sorted(PLATFORM_UNSUPPORTED_BASE_FIELDS),
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
            "platform_formula_fields": len(PLATFORM_FIELD_NAMES),
            "platform_catalog_fields": len(PLATFORM_CATALOG_FIELD_NAMES),
            "catalog_statement_fields": len(CATALOG_STATEMENT_FIELD_NAMES),
            "catalog_daily_technical_fields": len(CATALOG_DAILY_TECHNICAL_FIELD_NAMES),
            "platform_declared_fields": len(PLATFORM_DECLARED_FIELD_NAMES),
            "formula_names": len(statuses),
            "barra_fields_excluded": sorted(BARRA_FIELD_NAMES),
            "unsupported_base_fields": sorted(PLATFORM_UNSUPPORTED_BASE_FIELDS),
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
    "PandaAICatalogFieldSpec",
    "PandaAIFieldStore",
    "PLATFORM_FIELD_SET",
    "PLATFORM_FIELD_NAMES",
    "PLATFORM_FIELD_SPECS",
    "PLATFORM_CATALOG_FIELD_NAMES",
    "PLATFORM_CATALOG_SPECS",
    "CATALOG_STATEMENT_FIELD_NAMES",
    "CATALOG_DAILY_TECHNICAL_FIELD_NAMES",
    "PLATFORM_DECLARED_FIELD_NAMES",
    "BARRA_FIELD_NAMES",
    "PLATFORM_UNSUPPORTED_BASE_FIELDS",
    "build_pandaai_namespace",
    "formula_field_name_set",
    "is_platform_formula_field",
    "load_platform_field_specs",
    "split_formula_field_name",
]
