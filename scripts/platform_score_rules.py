#!/usr/bin/env python3
"""Single source of truth for the PandaAI pool scoring objective.

Provenance (verified 2026-09-24 against read-only arena endpoints):

* ``GET /arenaRanking/players/{participant_id}`` -> ``factor_pool_details``
  (snapshot ``51e08b952be8167a74ce1cac29a460bd``, published 2026-09-24T09:01:46Z)
  gives per-seat ``ic_mean`` / ``icir`` / ``ic_win_rate`` / ``s_i_a`` over 120
  periods, window ``20210927..20260826``.
* ``GET /arenaRanking/boards/points`` gives pool-level ``raw_a`` / ``na`` / ``nb``
  / ``nc`` / ``comb`` / points together with the anchors and denominators below.

Verified facts this module encodes:

1. ``s_i_a = |ic_mean| * |icir| * ic_win_rate`` reproduces all five seats of our
   pool exactly (see ``PLATFORM_SEAT_FIXTURE`` and ``self_test``).
2. The IR is the IR of the *RankIC series itself* (``mean(RankIC)/std(RankIC)``),
   not the Pearson-IC IR shown on the factor analysis page. The Pearson-IC IR
   understates our pool NA by about 26%.
3. The win rate counts periods whose *raw-orientation* RankIC is above
   ``+0.02``; it is not flipped by the seat's ``direction`` field (``size-only``
   is ``direction=negative`` yet ``ic_mean`` is positive and
   ``ic_win_rate = 74/120 = 0.6167``).
4. ``raw_a`` is the arithmetic mean of the counted seats' ``s_i_a``
   (``denominator_a`` = counted seats), so adding a seat raises NA iff its
   ``s_i_a`` exceeds the current mean.
5. Gates: ``pool_age_months == 0`` -> ``raw_b = 0``; fewer than
   ``MIN_SAMPLE_COUNT`` periods in the month -> SR = 0 -> ``raw_c = 0``.
6. A seat change always moves three things at once: ``na`` (immediate, the seat
   brings its own 120-period RankIC history), ``nb`` (steady level, plus a
   one-off first-period dilution while the pool has no out-of-sample month) and
   ``nc`` (the pool's new Rex / SR / MaxDD / turnover). Replacing the weakest
   seat is worth ~1.8x more than appending the same factor as a sixth seat.
   See ``seat_change_bridge`` / ``seat_change_turnover_points``.

This module is pure math: no credentials, no network, no backtests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd


SCORE_RULE_VERSION = "score-v2-seatbridge-20260924"
SCORE_RULES_DOCUMENT = "research_reports/platform_alignment/SCORE_RULES.md"

# Component anchors and combination weights (platform ``anchor_*`` / ``contribution_*``).
ANCHOR_A = 0.08
ANCHOR_B = 0.06
ANCHOR_C = 0.60
WEIGHT_A = 0.20
WEIGHT_B = 0.35
WEIGHT_C = 0.45

# Pool-level cap. The platform reports ``new_pool_cap = 0.70`` for our pool with
# ``pool_age_months = 0``; the exact month boundary is unverified, so callers
# should pass the platform value whenever it is known.
NEW_POOL_CAP = 0.70

# Raw-C inputs: turnover below the floor is free, monthly drawdown costs 1.2x.
TURNOVER_FLOOR_MONTHLY = 0.30
MAX_DRAWDOWN_PENALTY = 1.2

# A seat's win rate counts periods with RankIC above this threshold.
IC_WIN_THRESHOLD = 0.02
# Below this many periods in the month the platform reports SR = 0, hence NC = 0.
MIN_SAMPLE_COUNT = 2

POINTS_SCALE = 40_000.0
NEWBIE_FACTOR = 1.10

# Platform factor name -> local panel column. ``size_only`` is stored in raw
# orientation (RANK(MARKET_CAP)); the seat's ``direction=negative`` only decides
# which portfolio side is held and does not enter the A component.
LOCAL_SEAT_COLUMNS: Mapping[str, str] = {
    "t10-additions-20260911-T10-ADD-BM-20260911": "t10_size_plus_impact_bm",
    "VERIFY10-F260910-12": "book_to_market_lf_plus_impact",
    "VERIFY10-E260910-04": "book_to_market_lf_minus_size",
    "h03-t10-20260911-H03-T10-SINGLE": "impact60",
    "size-only-20260911-SIZE-ONLY-20260911": "size_only",
}

# Platform ``factor_pool_details`` of our pool (``mingle``), 2026-09-24 snapshot.
PLATFORM_SEAT_FIXTURE: tuple[Mapping[str, object], ...] = (
    {
        "factor_name": "t10-additions-20260911-T10-ADD-BM-20260911",
        "direction": "positive",
        "ic_mean": 0.11831931146342704,
        "icir": 0.6909021249785025,
        "ic_win_rate": 0.725,
        "s_i_a": 0.05926662119415439,
    },
    {
        "factor_name": "VERIFY10-E260910-04",
        "direction": "positive",
        "ic_mean": 0.079484870514664,
        "icir": 0.4286640209316829,
        "ic_win_rate": 0.6166666666666667,
        "s_i_a": 0.021011254255464188,
    },
    {
        "factor_name": "VERIFY10-F260910-12",
        "direction": "positive",
        "ic_mean": 0.07764396295464801,
        "icir": 0.4372634103393311,
        "ic_win_rate": 0.65,
        "s_i_a": 0.022068061621976547,
    },
    {
        "factor_name": "h03-t10-20260911-H03-T10-SINGLE",
        "direction": "positive",
        "ic_mean": 0.06481824766189923,
        "icir": 0.4268170051269225,
        "ic_win_rate": 0.65,
        "s_i_a": 0.017982594724007532,
    },
    {
        "factor_name": "size-only-20260911-SIZE-ONLY-20260911",
        "direction": "negative",
        "ic_mean": 0.05304846347882572,
        "icir": 0.2792604608998066,
        "ic_win_rate": 0.6166666666666667,
        "s_i_a": 0.009135508656026116,
    },
)

# Platform pool-level score of the same snapshot.
PLATFORM_POOL_FIXTURE: Mapping[str, float] = {
    "raw_a": 0.025892808090325757,
    "na": 0.32366010112907195,
    "nb": 0.0,
    "nc": 0.0,
    "comb": 0.06473202022581438,
    "points_before_newbie": 2589.2808090325752,
    "monthly_points": 2848.208889935833,
    "denominator_a": 5.0,
    "new_pool_cap": NEW_POOL_CAP,
    "newbie_factor": NEWBIE_FACTOR,
    "pool_age_months": 0.0,
    "sample_count": 120.0,
}


@dataclass(frozen=True)
class SeatStats:
    """Per-seat A-component statistics."""

    sample_count: int
    ic_mean: float
    icir: float
    win_rate: float
    s_i_a: float
    orientation: float
    insufficient: bool

    @property
    def counted(self) -> bool:
        """The platform counts a seat into ``raw_a`` when it is not insufficient."""
        return not self.insufficient

    def as_dict(self) -> dict[str, float]:
        return {
            "sample_count": float(self.sample_count),
            "ic_mean": self.ic_mean,
            "icir": self.icir,
            "win_rate": self.win_rate,
            "s_i_a": self.s_i_a,
            "orientation": self.orientation,
            "insufficient": float(self.insufficient),
        }


def _spearman(left: Sequence[float], right: Sequence[float]) -> float:
    """Spearman correlation with average ranks, matching the platform proxy."""
    x = pd.Series(np.asarray(left, dtype=float)).rank().to_numpy(dtype=float)
    y = pd.Series(np.asarray(right, dtype=float)).rank().to_numpy(dtype=float)
    x -= x.mean()
    y -= y.mean()
    denominator = float(np.sqrt((x * x).sum() * (y * y).sum()))
    if denominator <= 0.0:
        return float("nan")
    return float((x * y).sum() / denominator)


def rank_ic_series(
    frame: pd.DataFrame,
    *,
    date_column: str = "date",
    score_column: str = "score",
    return_column: str = "forward_return",
    min_cross_section: int = 100,
) -> pd.Series:
    """Cross-sectional Spearman RankIC per date.

    ``frame`` is a long panel with one row per (date, instrument). Rows whose
    score or forward return is not finite are dropped before ranking, and dates
    with fewer than ``min_cross_section`` valid rows are skipped.
    """
    series: dict[object, float] = {}
    for date, group in frame.groupby(date_column, sort=True):
        values = group[[score_column, return_column]].to_numpy(dtype=float)
        mask = np.isfinite(values).all(axis=1)
        if int(mask.sum()) < min_cross_section:
            continue
        series[date] = _spearman(values[mask, 0], values[mask, 1])
    return pd.Series(series, dtype=float)


def seat_stats(
    ic_values: Iterable[float],
    *,
    win_threshold: float = IC_WIN_THRESHOLD,
    min_sample_count: int = MIN_SAMPLE_COUNT,
) -> SeatStats:
    """Compute ``s_i_a`` from a RankIC series.

    ``orientation`` is the sign of the series mean; the win rate is the share of
    periods whose orientation-aligned RankIC exceeds ``win_threshold``.
    """
    values = np.asarray(
        [value for value in ic_values if value is not None and np.isfinite(value)],
        dtype=float,
    )
    count = int(values.size)
    if count == 0:
        return SeatStats(0, float("nan"), float("nan"), float("nan"), float("nan"), 0.0, True)
    ic_mean = float(values.mean())
    ic_std = float(values.std(ddof=0))
    icir = ic_mean / ic_std if ic_std > 0.0 else float("nan")
    orientation = 1.0 if ic_mean >= 0.0 else -1.0
    win_rate = float(np.mean(orientation * values > win_threshold))
    s_i_a = abs(ic_mean) * abs(icir) * win_rate if np.isfinite(icir) else float("nan")
    return SeatStats(
        sample_count=count,
        ic_mean=ic_mean,
        icir=icir,
        win_rate=win_rate,
        s_i_a=s_i_a,
        orientation=orientation,
        insufficient=count < min_sample_count,
    )


def counted_seats(seat_s_i: Iterable[float]) -> np.ndarray:
    """Seats whose ``s_i_a`` is finite and therefore enters ``raw_a``."""
    values = np.asarray([value for value in seat_s_i if np.isfinite(value)], dtype=float)
    return values


def mean_s_i(seat_s_i: Iterable[float]) -> float:
    values = counted_seats(seat_s_i)
    return float(values.mean()) if values.size else float("nan")


def raw_a(seat_s_i: Iterable[float]) -> float:
    """``raw_a`` is the arithmetic mean of the counted seats' ``s_i_a``."""
    return mean_s_i(seat_s_i)


def score_na(raw_a_value: float, *, cap: float = NEW_POOL_CAP, anchor: float = ANCHOR_A) -> float:
    return float(min(raw_a_value / anchor, cap))


def score_nb(
    seat_s_i: Iterable[float],
    *,
    pool_age_months: float,
    anchor: float = ANCHOR_B,
    cap: float = 1.0,
) -> float:
    """``nb`` needs at least one out-of-sample month; a new pool scores zero."""
    if pool_age_months < 1.0:
        return 0.0
    return float(min(mean_s_i(seat_s_i) / anchor, cap))


def raw_c_value(
    *,
    annual_excess_return: float,
    annual_sharpe: float,
    monthly_turnover: float,
    monthly_max_drawdown: float,
    sample_count: int,
    turnover_floor: float = TURNOVER_FLOOR_MONTHLY,
    drawdown_penalty: float = MAX_DRAWDOWN_PENALTY,
) -> float:
    """Raw C: risk-adjusted excess per unit of turnover, drawdown penalised."""
    if sample_count < MIN_SAMPLE_COUNT or annual_sharpe == 0.0:
        return 0.0
    turnover = max(float(monthly_turnover), float(turnover_floor))
    return (
        max(float(annual_excess_return), 0.0)
        / turnover
        * float(annual_sharpe)
        * (1.0 - drawdown_penalty * float(monthly_max_drawdown))
    )


def score_nc(raw_c: float, *, anchor: float = ANCHOR_C, cap: float = 1.0) -> float:
    return float(min(max(raw_c, 0.0) / anchor, cap))


def comb(na: float, nb: float, nc: float) -> float:
    return WEIGHT_A * na + WEIGHT_B * nb + WEIGHT_C * nc


def monthly_points(
    comb_value: float,
    *,
    is_newbie: bool = True,
    points_cap: float | None = None,
    scale: float = POINTS_SCALE,
    newbie_factor: float = NEWBIE_FACTOR,
) -> float:
    """Points for one month. ``points_cap`` applies before the newbie bonus."""
    points = comb_value * scale
    if points_cap is not None:
        points = min(points, points_cap)
    if is_newbie:
        points *= newbie_factor
    return float(points)


def component_points_per_001(component: str) -> float:
    """Monthly points for +0.01 of a single component (A=88, B=154, C=198)."""
    weights = {"a": WEIGHT_A, "b": WEIGHT_B, "c": WEIGHT_C}
    key = component.strip().lower()
    if key not in weights:
        raise ValueError(f"unknown component: {component!r}")
    return float(weights[key] * POINTS_SCALE * NEWBIE_FACTOR * 0.01)


def min_new_seat_s_i(seat_s_i: Iterable[float]) -> float:
    """Smallest ``s_i_a`` a new seat may have without lowering NA."""
    return mean_s_i(seat_s_i)


def marginal_na(
    seat_s_i: Iterable[float],
    new_seat_s_i: float,
    *,
    cap: float = NEW_POOL_CAP,
) -> float:
    """Change in ``na`` from appending a seat to the pool."""
    before = counted_seats(seat_s_i)
    after = np.append(before, float(new_seat_s_i))
    return score_na(mean_s_i(after), cap=cap) - score_na(mean_s_i(before), cap=cap)


def marginal_points(
    seat_s_i: Iterable[float],
    new_seat_s_i: float,
    *,
    cap: float = NEW_POOL_CAP,
    is_newbie: bool = True,
) -> float:
    """Monthly A-component points from appending a seat (NA delta only)."""
    before = counted_seats(seat_s_i)
    after = np.append(before, float(new_seat_s_i))
    delta = score_na(mean_s_i(after), cap=cap) - score_na(mean_s_i(before), cap=cap)
    return float(delta * WEIGHT_A * POINTS_SCALE * (NEWBIE_FACTOR if is_newbie else 1.0))


@dataclass(frozen=True)
class SeatChange:
    """Three-part account of adding or replacing a pool seat.

    ``d_na`` acts immediately (A re-scores the seat from its own 120-period
    RankIC history). ``d_nb_steady`` is the out-of-sample level change and only
    applies once ``pool_age_months >= 1``; ``first_period_dilution`` flags the
    one-off B cost of a seat whose live series starts from zero.  The C side is
    not included here - price it with ``nc_from_inputs`` on the pool inputs
    before and after the change.
    """

    seats_before: int
    seats_after: int
    d_raw_a: float
    d_na: float
    d_nb_steady: float
    first_period_dilution: bool
    points_na: float
    points_nb_steady: float

    @property
    def points_before_c(self) -> float:
        """A + B monthly points, ignoring the C side."""
        return self.points_na + self.points_nb_steady

    def as_dict(self) -> dict[str, float]:
        return {
            "seats_before": float(self.seats_before),
            "seats_after": float(self.seats_after),
            "d_raw_a": self.d_raw_a,
            "d_na": self.d_na,
            "d_nb_steady": self.d_nb_steady,
            "first_period_dilution": float(self.first_period_dilution),
            "points_na": self.points_na,
            "points_nb_steady": self.points_nb_steady,
            "points_before_c": self.points_before_c,
        }


def _remove_value(values: np.ndarray, target: float) -> np.ndarray:
    matches = np.isclose(values, float(target))
    if not matches.any():
        raise ValueError(f"seat {target!r} is not in the pool")
    index = int(np.argmax(matches))
    return np.delete(values, index)


def seat_change_bridge(
    seat_s_i: Iterable[float],
    *,
    added: float | None = None,
    removed: float | None = None,
    cap: float = NEW_POOL_CAP,
    pool_age_months: float = 0.0,
    is_newbie: bool = True,
    nb_active: bool | None = None,
) -> SeatChange:
    """Add and/or replace seats and return the A/B part of the delta.

    Replacing the weakest seat beats adding a seat with the same ``s_i_a``
    because ``raw_a`` is an arithmetic mean: removing a weak denominator entry
    lifts every remaining seat.  Verified example (2026-09-24 pool): replacing
    ``size_only`` (0.00914) with a 0.0585 seat gives +1,086 NA points/month and
    +2,534 steady NB points/month, versus +598 / +1,395 for adding the same
    seat as a sixth seat.
    """
    before = counted_seats(seat_s_i)
    if before.size == 0:
        raise ValueError("pool has no counted seats")
    after = before
    if removed is not None:
        after = _remove_value(after, float(removed))
    if added is not None:
        after = np.append(after, float(added))
    if after.size == 0:
        raise ValueError("change would leave the pool with no counted seats")

    d_raw_a = float(after.mean() - before.mean())
    d_na = score_na(float(after.mean()), cap=cap) - score_na(float(before.mean()), cap=cap)
    d_nb_steady = d_raw_a / ANCHOR_B
    if nb_active is None:
        nb_active = pool_age_months >= 1.0
    if not nb_active:
        d_nb_steady = 0.0
    points_na = d_na * WEIGHT_A * POINTS_SCALE * (NEWBIE_FACTOR if is_newbie else 1.0)
    points_nb = d_nb_steady * WEIGHT_B * POINTS_SCALE * (NEWBIE_FACTOR if is_newbie else 1.0)
    return SeatChange(
        seats_before=int(before.size),
        seats_after=int(after.size),
        d_raw_a=d_raw_a,
        d_na=d_na,
        d_nb_steady=d_nb_steady,
        first_period_dilution=added is not None and pool_age_months < 1.0,
        points_na=float(points_na),
        points_nb_steady=float(points_nb),
    )


def nc_from_inputs(
    *,
    annual_excess_return: float,
    annual_sharpe: float,
    monthly_turnover: float,
    monthly_max_drawdown: float,
    sample_count: int = MIN_SAMPLE_COUNT,
) -> float:
    """Pool ``nc`` from the four monthly inputs (the C side of a seat change)."""
    return score_nc(
        raw_c_value(
            annual_excess_return=annual_excess_return,
            annual_sharpe=annual_sharpe,
            monthly_turnover=monthly_turnover,
            monthly_max_drawdown=monthly_max_drawdown,
            sample_count=sample_count,
        )
    )


def seat_change_turnover_points(
    *,
    annual_excess_return: float,
    annual_sharpe: float,
    monthly_max_drawdown: float,
    turnover_before: float,
    turnover_after: float,
    is_newbie: bool = True,
) -> float:
    """Monthly points lost/gained on the C side from a pool turnover change.

    ``max(turnover, 0.30)`` means the first 0.30 of monthly turnover is free.
    """
    before = nc_from_inputs(
        annual_excess_return=annual_excess_return,
        annual_sharpe=annual_sharpe,
        monthly_turnover=turnover_before,
        monthly_max_drawdown=monthly_max_drawdown,
    )
    after = nc_from_inputs(
        annual_excess_return=annual_excess_return,
        annual_sharpe=annual_sharpe,
        monthly_turnover=turnover_after,
        monthly_max_drawdown=monthly_max_drawdown,
    )
    return float(
        (after - before) * WEIGHT_C * POINTS_SCALE * (NEWBIE_FACTOR if is_newbie else 1.0)
    )


def self_test() -> dict[str, float]:
    """Assert the verified platform identities; return the reproduced values."""
    seats = PLATFORM_SEAT_FIXTURE
    reproduced = []
    for seat in seats:
        s_i = abs(float(seat["ic_mean"])) * abs(float(seat["icir"])) * float(seat["ic_win_rate"])
        expected = float(seat["s_i_a"])
        assert abs(s_i - expected) <= 1e-12 * max(1.0, abs(expected)) + 1e-15, (
            seat["factor_name"],
            s_i,
            expected,
        )
        reproduced.append(s_i)

    seat_s_i = np.asarray(reproduced, dtype=float)
    raw_a_value = raw_a(seat_s_i)
    assert abs(raw_a_value - PLATFORM_POOL_FIXTURE["raw_a"]) < 1e-15, raw_a_value

    na = score_na(raw_a_value, cap=PLATFORM_POOL_FIXTURE["new_pool_cap"])
    assert abs(na - PLATFORM_POOL_FIXTURE["na"]) < 1e-15, na

    nb = score_nb(seat_s_i, pool_age_months=PLATFORM_POOL_FIXTURE["pool_age_months"])
    assert nb == PLATFORM_POOL_FIXTURE["nb"], nb

    nc_probe = raw_c_value(
        annual_excess_return=0.1,
        annual_sharpe=1.0,
        monthly_turnover=0.5,
        monthly_max_drawdown=0.01,
        sample_count=1,
    )
    assert nc_probe == 0.0, nc_probe
    nc = score_nc(nc_probe)
    assert nc == PLATFORM_POOL_FIXTURE["nc"], nc

    comb_value = comb(na, nb, nc)
    assert abs(comb_value - PLATFORM_POOL_FIXTURE["comb"]) < 1e-15, comb_value

    points = monthly_points(comb_value, is_newbie=True)
    assert abs(points - PLATFORM_POOL_FIXTURE["monthly_points"]) < 1e-9, points
    points_before = monthly_points(comb_value, is_newbie=False)
    assert abs(points_before - PLATFORM_POOL_FIXTURE["points_before_newbie"]) < 1e-9, points_before

    for component, expected in (("a", 88.0), ("b", 154.0), ("c", 198.0)):
        assert abs(component_points_per_001(component) - expected) < 1e-9, component

    threshold = min_new_seat_s_i(seat_s_i)
    assert abs(threshold - raw_a_value) < 1e-15, threshold
    assert marginal_na(seat_s_i, threshold) == 0.0
    assert marginal_na(seat_s_i, threshold + 0.01) > 0.0
    assert marginal_na(seat_s_i, threshold - 0.01) < 0.0
    assert marginal_points(seat_s_i, threshold + 0.01) > 0.0

    local_seat_columns = dict(LOCAL_SEAT_COLUMNS)
    assert len(local_seat_columns) == len(seats) == 5

    # Seat change: replacing the weakest seat beats adding the same factor.
    weakest = float(seat_s_i.min())
    replaced = seat_change_bridge(seat_s_i, removed=weakest, added=0.0585, pool_age_months=1.0)
    assert abs(replaced.d_raw_a - (0.0585 - weakest) / seat_s_i.size) < 1e-12, replaced
    assert replaced.seats_before == 5 and replaced.seats_after == 5
    appended = seat_change_bridge(seat_s_i, added=0.0585, pool_age_months=1.0)
    assert appended.seats_after == 6
    assert replaced.points_before_c > appended.points_before_c > 0.0, (replaced, appended)

    # NB is gated while the pool has no out-of-sample month.
    gated = seat_change_bridge(seat_s_i, removed=weakest, added=0.0585, pool_age_months=0.0)
    assert gated.d_nb_steady == 0.0 and gated.first_period_dilution is True, gated
    assert gated.points_na == replaced.points_na

    # Turnover: the first 0.30 of monthly turnover is free.
    free = seat_change_turnover_points(
        annual_excess_return=0.2030,
        annual_sharpe=1.0648,
        monthly_max_drawdown=0.0459,
        turnover_before=0.29,
        turnover_after=0.30,
    )
    assert abs(free) < 1e-9, free
    cost = seat_change_turnover_points(
        annual_excess_return=0.2030,
        annual_sharpe=1.0648,
        monthly_max_drawdown=0.0459,
        turnover_before=0.30,
        turnover_after=0.50,
    )
    assert cost < 0.0, cost

    return {
        "raw_a": raw_a_value,
        "na": na,
        "nb": nb,
        "nc": nc,
        "comb": comb_value,
        "points": points,
        "min_new_seat_s_i": threshold,
        "replace_weakest_points": replaced.points_before_c,
        "append_sixth_points": appended.points_before_c,
        "turnover_030_to_050_points": cost,
    }


def main(argv: Sequence[str] | None = None) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="verify the platform fixtures")
    parser.parse_args(argv)

    payload = {
        "score_rule_version": SCORE_RULE_VERSION,
        "self_test": self_test(),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
