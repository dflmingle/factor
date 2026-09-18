from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from factor_formula_dedupe import normalize_formula


def test_vwap_expansion_is_a_duplicate() -> None:
    assert normalize_formula("Div($vwap,$high)") == normalize_formula(
        "Div(Div($amount,$volume),$high)"
    )
    assert normalize_formula("AMOUNT / VOLUME / HIGH") == normalize_formula(
        "Div($vwap,$high)"
    )


def test_commutative_rewrites_are_a_duplicate() -> None:
    assert normalize_formula("Add(CLOSE, OPEN)") == normalize_formula("OPEN+CLOSE")
    assert normalize_formula("Mul(CLOSE, OPEN)") == normalize_formula("OPEN*CLOSE")


def test_inverse_rewrites_are_a_duplicate() -> None:
    assert normalize_formula("Inv(CURRENT_ASSETS)") == normalize_formula(
        "1/CURRENT_ASSETS"
    )
    assert normalize_formula("Sub(0, CLOSE)") == normalize_formula("-CLOSE")


def test_non_equivalent_order_is_preserved() -> None:
    assert normalize_formula("CLOSE/OPEN") != normalize_formula("OPEN/CLOSE")
    assert normalize_formula("CLOSE-OPEN") != normalize_formula("OPEN-CLOSE")


def test_same_window_rolling_extreme_is_idempotent() -> None:
    assert normalize_formula("TS_MAX(TS_MAX(CURRENT_LIABILITIES,40),40)") == normalize_formula(
        "TS_MAX(CURRENT_LIABILITIES,40)"
    )
