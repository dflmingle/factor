from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import torch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from alphaprobe_gfn_tushare import (  # noqa: E402
    ObjectiveAlphaPoolGFN,
    scaled_net_excess_reward,
)
from alphaprobe_gp_tushare import AlignedNetExcessContext  # noqa: E402


def test_scaled_net_excess_reward_preserves_sign_and_is_bounded() -> None:
    assert scaled_net_excess_reward(0.10, weight=0.10, scale=0.10) > 0.0
    assert scaled_net_excess_reward(-0.10, weight=0.10, scale=0.10) < 0.0
    assert abs(scaled_net_excess_reward(100.0, weight=0.10, scale=0.10)) <= 0.10
    assert scaled_net_excess_reward(None, weight=0.10, scale=0.10) == -0.10
    assert scaled_net_excess_reward(float("nan"), weight=0.10, scale=0.10) == -0.10
    assert scaled_net_excess_reward(0.10, weight=0.0, scale=0.10) == 0.0


def test_objective_pool_reads_net_excess_once_and_records_stats() -> None:
    calls: list[torch.Tensor] = []

    class Context:
        def score(self, value: torch.Tensor) -> dict[str, float]:
            calls.append(value)
            return {"net_excess": -0.05}

    pool = ObjectiveAlphaPoolGFN.__new__(ObjectiveAlphaPoolGFN)
    pool.net_excess_context = Context()
    pool.net_excess_weight = 0.10
    pool.net_excess_scale = 0.10
    pool.last_net_excess_stats = None

    value = torch.ones((2, 3), dtype=torch.float32)
    reward = pool._net_excess_reward(value)

    assert reward < 0.0
    assert len(calls) == 1
    assert pool.last_net_excess_stats == {"net_excess": -0.05}


def test_aligned_net_excess_uses_cost_adjusted_top_group() -> None:
    dates = pd.date_range("2024-01-01", periods=15, freq="D")
    instruments = [f"{index:06d}.SZ" for index in range(20)]
    rows: list[dict[str, object]] = []
    for date_index, date in enumerate(dates):
        interval = max((date_index - 1) // 2, 0)
        for stock_index, instrument in enumerate(instruments):
            close = 100.0 * (1.10**interval) if stock_index < 10 else 100.0
            rows.append(
                {
                    "date": date,
                    "instrument": instrument,
                    "close_qfq": close,
                    "total_mv": 1.0,
                }
            )
    frame = pd.DataFrame(rows)
    data = SimpleNamespace(
        _stock_ids=pd.Index(instruments),
        _evaluation_dates=list(dates),
        device=torch.device("cpu"),
    )
    context = AlignedNetExcessContext(
        frame=frame,
        calendar=list(dates),
        data=data,
        start_date=dates[0],
        end_date=dates[-1],
        cycle=2,
        label_offset=1,
        groups=2,
        round_trip_cost=0.006,
    )
    factor = torch.zeros((len(dates), len(instruments)), dtype=torch.float32)
    factor[:, :10] = 1.0

    stats = context.score(factor)

    assert stats["periods"] == 6
    assert stats["gross_excess"] is not None and stats["gross_excess"] > 0.0
    assert stats["turnover"] == 0.0
    assert stats["annual_cost"] == 0.0
    assert np.isclose(stats["net_excess"], stats["gross_excess"])
