#!/usr/bin/env python3
"""Run AlphaPROBE GFlowNet mining on the local Tushare full-A snapshot.

The search policy and expression environment come from AlphaPROBE.  Only the
data adapter is local: it reads the project's qfq Parquet cache, joins the
same-day ``daily_basic`` universe, and adds VWAP from cached amount/volume.
The target follows the platform-alignment label:
``close(t+1) -> close(t+1+cycle)``.

Use ``--dry-run`` to validate the cache and GFlowNet wiring without training.
Training is intentionally explicit because it is GPU and data intensive.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import torch
from torch_geometric.data import Batch, Data


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALPHAPROBE_ROOT = PROJECT_ROOT / "quantlab" / "third_party" / "AlphaPROBE"
ALPHAPROBE_SRC = ALPHAPROBE_ROOT / "src"
if str(ALPHAPROBE_SRC) not in sys.path:
    sys.path.insert(0, str(ALPHAPROBE_SRC))

from alphagen.data.expression import Feature, FeatureType, Ref  # noqa: E402
from alphagen.data.tokens import (  # noqa: E402
    BEG_TOKEN,
    SEP_TOKEN,
    ConstantToken,
    DeltaTimeToken,
    FeatureToken,
    OperatorToken,
    Token,
)
from alphagen.data.tree import (  # noqa: E402
    ExpressionBuilder,
    InvalidExpressionException,
    OutOfDataRangeError,
)
from alphagen.utils.correlation import batch_pearsonr  # noqa: E402
from alpha_gfn.alpha_pool import AlphaPoolGFN  # noqa: E402
from alpha_gfn.config import (  # noqa: E402
    CONSTANTS,
    DELTA_TIMES,
    FEATURES,
    HIDDEN_DIM,
    MAX_EXPR_LENGTH,
    OPERATORS,
)
from alpha_gfn.env.core import GFNEnvCore  # noqa: E402
from alpha_gfn.gflownet import EntropyTBGFlowNet  # noqa: E402
from alpha_gfn.modules import SequenceEncoder  # noqa: E402
from alpha_gfn.preprocessors import IntegerPreprocessor  # noqa: E402
from alphaprobe_gp_tushare import TushareStockData, load_trade_dates  # noqa: E402
from full_a_local_data import load_full_a_data  # noqa: E402
from gfn.actions import Actions  # noqa: E402
from gfn.env import DiscreteEnv  # noqa: E402
from gfn.states import DiscreteStates  # noqa: E402
from pandaai_fields_local import (  # noqa: E402
    PRICE_VOLUME_FIELDS,
    PandaAIField,
)
from platform_alignment_rules import (  # noqa: E402
    ALIGNMENT_DATA_START,
    ALIGNMENT_END,
    ALIGNMENT_LABEL_OFFSET,
    ALIGNMENT_RULES_DOCUMENT,
    ALIGNMENT_RULE_VERSION,
    alignment_config_snapshot,
    validate_alignment_config,
)

try:  # noqa: E402
    from gfn.gflownet.trajectory_balance import TBGFlowNet
    from gfn.modules import DiscretePolicyEstimator
    from gfn.samplers import Sampler
except ModuleNotFoundError as exc:  # pragma: no cover - depends on local environment
    raise SystemExit(
        "AlphaPROBE GFlowNet dependencies are missing. Install the AlphaPROBE "
        "runtime with: python -m pip install 'torchgfn>=1.2.1' "
        "'torch-geometric>=2.6.1' 'gymnasium>=1.2.0'"
    ) from exc


DEFAULT_CACHE_ROOT = PROJECT_ROOT / "quantlab" / ".quantlab" / "cache" / "research" / "cn_equity"
DEFAULT_PRICE_ROOT = DEFAULT_CACHE_ROOT / "tushare_factor_recheck" / "qfq" / "daily_batches"
DEFAULT_CAP_ROOT = DEFAULT_CACHE_ROOT / "tushare_factor_recheck" / "daily_basic_full_a"
DEFAULT_FINANCIAL_ROOT = DEFAULT_CACHE_ROOT / "financial_full_a"
DEFAULT_OUTPUT = DEFAULT_CACHE_ROOT / "reports" / "alphaprobe_gfn_tushare_cycle5_signed_positive"

# Keep the default fundamental action space useful for research without making
# a single run compete across thousands of statement-period variants.
FUNDAMENTAL_CORE_FIELDS = (
    "market_cap_3",
    "pb_ratio_ttm",
    "pb_ratio_lf",
    "book_to_market_ratio_ttm",
    "book_to_market_ratio_lf",
    "ps_ratio_ttm",
    "ev_ttm",
    "revenue_ttm",
    "operating_revenue_ttm",
    "net_profit_ttm",
    "net_profit_deduct_non_recurring_pnl_ttm",
    "total_assets_ttm",
    "total_liabilities_ttm",
    "equity_parent_company_ttm",
    "cash_flow_from_operating_activities_ttm",
    "gross_profit_ttm",
    "profit_from_operation_ttm",
)
BASE_FEATURE_NAMES = frozenset(feature.name.lower() for feature in FEATURES) | PRICE_VOLUME_FIELDS
FIELD_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class ObjectiveAlphaPoolGFN(AlphaPoolGFN):
    """AlphaPool with an explicit signed-IC objective.

    AlphaPROBE's bundled pool takes ``abs`` of both the return IC and mutual
    IC.  For positive-IC mining, the return IC must retain its sign while
    mutual correlation remains absolute so inverse duplicates are still
    treated as redundant.  The original absolute behavior is kept as an
    explicit compatibility mode.
    """

    VALID_OBJECTIVES = frozenset({"signed_positive", "absolute"})

    def __init__(self, *args: Any, ic_objective: str = "signed_positive", **kwargs: Any):
        if ic_objective not in self.VALID_OBJECTIVES:
            choices = ", ".join(sorted(self.VALID_OBJECTIVES))
            raise ValueError(f"ic-objective must be one of: {choices}")
        super().__init__(*args, **kwargs)
        self.ic_objective = ic_objective

    def _score_single_ic(self, ic_ret: float) -> float:
        return float(abs(ic_ret) if self.ic_objective == "absolute" else ic_ret)

    def try_new_expr(self, expr: object, embedding: torch.Tensor | None = None) -> tuple[float, float]:
        value = self._normalize_by_day(expr.evaluate(self.data))
        ic_ret, ic_mut = self._calc_ics(value, ic_mut_threshold=0.99)
        if ic_ret is None or ic_mut is None:
            return 0.0, 1.0

        raw_ic = float(ic_ret)
        score_ic = self._score_single_ic(raw_ic)
        mutual_ics = np.abs(ic_mut)

        # A non-positive candidate is not useful for a signed positive-IC
        # pool.  Return its signed score so the environment can assign the
        # minimum reward, and keep it out of the pool entirely.
        if self.ic_objective == "signed_positive" and raw_ic <= 0.0:
            print(f"[Pool Reject non-positive IC={raw_ic:.6f}] {expr}")
            return score_ic, 0.0

        if self.size < self.capacity:
            if mutual_ics.size == 0 or np.max(mutual_ics) <= self.ic_mut_threshold:
                self._add_factor(expr, value, score_ic, mutual_ics, embedding)
                print(f"[Pool Add] {expr}")
            else:
                print(f"[Pool Reject correlated] {expr}")
        else:
            min_ic_idx = np.argmin(self.single_ics[:self.size])
            min_ic = self.single_ics[min_ic_idx]

            if score_ic > min_ic and (mutual_ics.size == 0 or np.max(mutual_ics) <= self.ic_mut_threshold):
                self._add_factor(expr, value, score_ic, mutual_ics, embedding)
                print(f"[Pool Add] {expr}")
                print(f"[Pool Pop] {self.exprs[np.argmin(self.single_ics[:self.size])]}")
                self._pop()
            else:
                print(f"[Pool Reject] {expr}")

        novelty = (1 - np.max(mutual_ics)) if mutual_ics.size > 0 else 1.0
        return score_ic, float(novelty)

    def try_new_expr_with_ssl(
        self, expr: object, embedding: torch.Tensor | None = None
    ) -> tuple[float, float, float]:
        ic_reward, nov_reward = self.try_new_expr(expr, embedding)

        # Do not let auxiliary SSL/novelty terms turn a non-positive IC into
        # a high-reward trajectory in the signed-positive objective.
        if self.ic_objective == "signed_positive" and ic_reward <= 0.0:
            return ic_reward, 0.0, 0.0

        ssl_reward = self.compute_ssl_reward(expr, embedding) if embedding is not None else 0.0
        return ic_reward, nov_reward, ssl_reward


class GFNNamedField(PandaAIField):
    """PandaAI local field rendered in AlphaPROBE's ``$field`` syntax."""

    def __str__(self) -> str:
        return f"${self.field_name}"


class NamedFieldToken(Token):
    """Token for a PIT/TTM field that is not part of FeatureType."""

    def __init__(self, field_name: str) -> None:
        normalized = str(field_name).strip().lower()
        if FIELD_NAME_PATTERN.fullmatch(normalized) is None:
            raise ValueError(f"Invalid named field: {field_name}")
        self.field_name = normalized

    def __str__(self) -> str:
        return f"${self.field_name}"


class GFNExpressionBuilder(ExpressionBuilder):
    """ExpressionBuilder with lazy local PandaAI field leaves."""

    def add_token(self, token: Token) -> None:
        if isinstance(token, NamedFieldToken):
            if not self.validate(token):
                raise InvalidExpressionException(
                    f"Token {token} not allowed here, stack: {self.stack}."
                )
            self.stack.append(GFNNamedField(token.field_name))
            return
        super().add_token(token)

    def validate(self, token: Token) -> bool:
        if isinstance(token, NamedFieldToken):
            return self.validate_feature()
        return super().validate(token)


class GFNExpressionParser:
    """Parse AlphaPROBE formulas plus the selected local named fields."""

    def __init__(self, named_fields: Iterable[str] = ()) -> None:
        self.named_fields = {
            str(field).strip().lower()
            for field in named_fields
            if FIELD_NAME_PATTERN.fullmatch(str(field).strip().lower())
        }

    def tokenize(self, expr: str) -> list[Token]:
        operator_map = {operator.__name__: operator for operator in OPERATORS}
        feature_map = {
            f"${feature.name.lower()}": feature
            for feature in FEATURES
        }
        tokens: list[Token] = []

        def split_arguments(args_str: str) -> list[str]:
            args: list[str] = []
            current: list[str] = []
            depth = 0
            for char in args_str:
                if char == "(":
                    depth += 1
                elif char == ")":
                    depth -= 1
                if char == "," and depth == 0:
                    args.append("".join(current).strip())
                    current = []
                else:
                    current.append(char)
            if current and "".join(current).strip():
                args.append("".join(current).strip())
            return args

        def parse_expression(expr_str: str) -> None:
            value = expr_str.strip()
            lowered = value.lower()
            if lowered in feature_map:
                tokens.append(FeatureToken(feature_map[lowered]))
                return

            field_name = lowered[1:] if lowered.startswith("$") else lowered
            if field_name in self.named_fields:
                tokens.append(NamedFieldToken(field_name))
                return

            if re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", value):
                number = float(value)
                if re.fullmatch(r"[+-]?\d+", value):
                    tokens.append(DeltaTimeToken(int(number)))
                else:
                    tokens.append(ConstantToken(number))
                return

            if "(" in value and value.endswith(")"):
                function_name = value[: value.find("(")].strip()
                operator = operator_map.get(function_name)
                if operator is None:
                    raise ValueError(f"Unknown operator: {function_name}")
                arguments = split_arguments(value[value.find("(") + 1 : value.rfind(")")])
                for argument in arguments:
                    parse_expression(argument)
                tokens.append(OperatorToken(operator))
                return

            raise ValueError(f"Invalid expression: {value}")

        parse_expression(expr)
        return tokens

    def parse(self, expr: str) -> object:
        builder = GFNExpressionBuilder()
        for token in self.tokenize(expr):
            builder.add_token(token)
        return builder.get_tree()


class NamedFieldSequenceEncoder(SequenceEncoder):
    """SequenceEncoder whose GNN path understands the extended action map."""

    def set_action_tokens(self, action_tokens: dict[int, Token]) -> None:
        self.action_tokens = action_tokens

    def _build_named_graph(self, token_ids: list[int]) -> Data:
        if not hasattr(self, "action_tokens"):
            raise RuntimeError("The GNN encoder has no action-token map")
        device = self.token_embedding.weight.device
        tokens = [self.action_tokens[token_id] for token_id in token_ids]
        edges: list[tuple[int, int]] = []
        edge_types: list[int] = []
        stack: list[int] = []
        unary_ops = {"Abs", "SLog1p", "Inv", "Sign", "Log", "Rank"}
        commutative_ops = {"Add", "Mul"}
        non_commutative_ops = {
            "Sub",
            "Div",
            "Pow",
            "Greater",
            "Less",
            "GetGreater",
            "GetLess",
        }
        rolling_ops = {
            "Ref",
            "TsMean",
            "TsSum",
            "TsStd",
            "TsIr",
            "TsMinMaxDiff",
            "TsMaxDiff",
            "TsMinDiff",
            "TsVar",
            "TsSkew",
            "TsKurt",
            "TsMax",
            "TsMin",
            "TsMed",
            "TsMad",
            "TsRank",
            "TsDelta",
            "TsDiv",
            "TsPctChange",
            "TsWMA",
            "TsEMA",
        }
        pair_rolling_ops = {"TsCov", "TsCorr"}

        for node_index, token in enumerate(tokens):
            if isinstance(token, OperatorToken):
                operator_name = token.operator.__name__
                n_args = token.operator.n_args()
                if len(stack) >= n_args:
                    for argument_index in range(n_args):
                        child_index = stack.pop()
                        edges.append((child_index, node_index))
                        if operator_name in unary_ops:
                            edge_types.append(0)
                        elif operator_name in commutative_ops:
                            edge_types.append(1)
                        elif operator_name in non_commutative_ops:
                            edge_types.append(3 if argument_index == 0 else 2)
                        elif operator_name in rolling_ops or operator_name in pair_rolling_ops:
                            edge_types.append(5 if argument_index == 0 else 4)
                        else:
                            edge_types.append(0)
            stack.append(node_index)

        if edges:
            edge_index = torch.tensor(edges, dtype=torch.long, device=device).t().contiguous()
            edge_type = torch.tensor(edge_types, dtype=torch.long, device=device)
        else:
            edge_index = torch.empty((2, 0), dtype=torch.long, device=device)
            edge_type = torch.empty((0,), dtype=torch.long, device=device)
        ids = torch.tensor(token_ids, dtype=torch.long, device=device)
        return Data(x=self.token_embedding(ids), edge_index=edge_index, edge_type=edge_type)

    def forward(self, state_tokens: torch.Tensor) -> torch.Tensor:
        if self.encoder_type != "gnn":
            return super().forward(state_tokens)
        data_list = [
            self._build_named_graph([token_id for token_id in row.tolist() if token_id > -1])
            for row in state_tokens
        ]
        return self.encoder(Batch.from_data_list(data_list))


def parse_date(value: str) -> pd.Timestamp:
    text = str(value).strip()
    parsed = pd.to_datetime(
        text,
        format="%Y%m%d" if len(text) == 8 and text.isdigit() else None,
        errors="raise",
    )
    return pd.Timestamp(parsed).normalize()


def date_text(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def json_default(value: object) -> object:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().tolist()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


class TushareGFNStockData(TushareStockData):
    """Add the VWAP feature required by AlphaPROBE's GFlowNet action space."""

    @classmethod
    def from_aligned_frame_with_vwap(
        cls,
        *,
        frame: pd.DataFrame,
        calendar: list[pd.Timestamp],
        instrument: list[str],
        start_time: str,
        end_time: str,
        max_backtrack_days: int,
        max_future_days: int,
        device: torch.device,
        financial_root: Path | None = None,
    ) -> "TushareGFNStockData":
        obj = super().from_aligned_frame(
            frame=frame,
            calendar=calendar,
            instrument=instrument,
            start_time=start_time,
            end_time=end_time,
            max_backtrack_days=max_backtrack_days,
            max_future_days=max_future_days,
            device=device,
            financial_root=financial_root,
        )

        indexed = frame.set_index(["date", "instrument"])
        volume = pd.to_numeric(indexed["volume"], errors="coerce")
        amount = pd.to_numeric(indexed["amount"], errors="coerce")
        vwap = amount.where(volume.gt(0)).div(volume.where(volume.gt(0)))

        real_dates = obj._pre_dates + obj._evaluation_dates + obj._post_dates
        real_index = pd.DatetimeIndex(real_dates)
        stock_index = obj._stock_ids
        wide = vwap.unstack("instrument").reindex(index=real_index, columns=stock_index).ffill()
        feature_values = wide.to_numpy(dtype=np.float32, copy=True)
        start = obj._pre_padding
        stop = start + len(real_dates)
        obj.data[start:stop, int(FeatureType.VWAP), :] = torch.as_tensor(
            feature_values,
            dtype=torch.float32,
            device=device,
        )
        obj.vwap_source = frame.attrs.get("market_field_sources", {}).get(
            "amount",
            "Tushare amount / volume",
        )
        return obj


def build_target(cycle: int) -> object:
    """Build the label-1 forward return used by the local alignment contract."""
    if cycle < 1:
        raise ValueError("cycle must be at least 1")
    close = Feature(FeatureType.CLOSE)
    entry = Ref(close, -ALIGNMENT_LABEL_OFFSET)
    exit_ = Ref(close, -(ALIGNMENT_LABEL_OFFSET + cycle))
    return exit_ / entry - 1


def resolve_device(value: str) -> torch.device:
    if value == "auto":
        return torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    device = torch.device(value)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError(f"Requested {device}, but CUDA is not available")
    return device


def build_panel(
    *,
    frame: pd.DataFrame,
    calendar: list[pd.Timestamp],
    instruments: list[str],
    start: str,
    end: str,
    backtrack_days: int,
    future_days: int,
    device: torch.device,
    financial_root: Path,
) -> TushareGFNStockData:
    return TushareGFNStockData.from_aligned_frame_with_vwap(
        frame=frame,
        calendar=calendar,
        instrument=instruments,
        start_time=start,
        end_time=end,
        max_backtrack_days=backtrack_days,
        max_future_days=future_days,
        device=device,
        financial_root=financial_root,
    )


def safe_batch_spearmanr(x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
    """Compute daily Spearman correlation without a stock-by-stock tensor."""
    valid = torch.isfinite(x) & torch.isfinite(y)

    def rank_rows(values: torch.Tensor) -> torch.Tensor:
        sortable = torch.where(valid, values, torch.full_like(values, float("inf")))
        order = torch.argsort(sortable, dim=1)
        sorted_values = torch.gather(sortable, 1, order)
        sorted_valid = torch.gather(valid, 1, order)

        new_group = torch.ones_like(sorted_valid, dtype=torch.bool)
        if sorted_values.shape[1] > 1:
            new_group[:, 1:] = (
                ~sorted_valid[:, 1:]
                | ~sorted_valid[:, :-1]
                | (sorted_values[:, 1:] != sorted_values[:, :-1])
            )
        group_ids = new_group.cumsum(dim=1) - 1
        positions = torch.arange(
            sorted_values.shape[1], device=values.device, dtype=values.dtype
        ).expand_as(sorted_values)
        sums = torch.zeros_like(sorted_values).scatter_add(1, group_ids, positions)
        counts = torch.zeros_like(sorted_values).scatter_add(
            1, group_ids, torch.ones_like(sorted_values)
        )
        average_ranks = sums / counts.clamp_min(1)
        ranks = torch.zeros_like(values).scatter(1, order, average_ranks)
        ranks[~valid] = torch.nan
        return ranks

    return batch_pearsonr(rank_rows(x), rank_rows(y))


def parse_field_list(value: str | Path | None) -> list[str]:
    if value is None:
        return []
    raw_value = str(value)
    candidate = Path(raw_value).expanduser()
    try:
        is_file = candidate.is_file()
    except OSError:
        # A saved evaluator run may pass a long comma-separated field list;
        # do not let Path.stat reject it before the list parser sees it.
        is_file = False
    if is_file:
        raw_values = candidate.read_text(encoding="utf-8").splitlines()
    else:
        raw_values = [raw_value]
    fields: list[str] = []
    for raw_line in raw_values:
        line = raw_line.split("#", 1)[0].strip().lower()
        if not line:
            continue
        fields.extend(item for item in line.replace(",", " ").split() if item)
    return list(dict.fromkeys(fields))


def resolve_search_fields(
    panel: TushareGFNStockData,
    *,
    feature_set: str,
    extra_fields: str | Path | None,
    max_extra_fields: int,
) -> dict[str, Any]:
    """Resolve and validate the named-field action space for one run."""
    requested_override = parse_field_list(extra_fields)
    if requested_override:
        requested = requested_override
        resolved_feature_set = "custom"
    elif feature_set == "price_volume":
        return {
            "feature_set": feature_set,
            "search_fields": [],
            "search_field_count": 0,
            "search_field_status": [],
        }
    elif feature_set == "fundamental_core":
        requested = list(FUNDAMENTAL_CORE_FIELDS)
        resolved_feature_set = feature_set
    elif feature_set == "all_active":
        active = set(panel.pandaai_field_store.active_search_fields(include_period_variants=True))
        requested = sorted(active - BASE_FEATURE_NAMES)
        resolved_feature_set = feature_set
    else:
        raise ValueError(f"Unsupported feature-set: {feature_set}")

    requested = [field for field in requested if field not in BASE_FEATURE_NAMES]
    if feature_set == "all_active" and not requested_override:
        unavailable = []
        statuses = [panel.pandaai_field_store.status(field) for field in requested]
    else:
        statuses = [panel.pandaai_field_store.status(field) for field in requested]
        unavailable = [
            str(item["field"])
            for item in statuses
            if item["status"] == "unavailable"
        ]
    if unavailable:
        details = [item for item in statuses if item["field"] in unavailable]
        detail_text = "; ".join(
            f"{item['field']}: {item['note'] or item['status']}" for item in details
        )
        raise ValueError(
            "Requested named fields are unavailable in the local financial cache: "
            f"{detail_text}"
        )
    if max_extra_fields < 0:
        raise ValueError("--max-extra-fields must be non-negative; use 0 for no limit")
    if max_extra_fields and len(requested) > max_extra_fields:
        raise ValueError(
            f"Feature set {resolved_feature_set} resolves to {len(requested)} named fields, "
            f"above --max-extra-fields={max_extra_fields}; use a field file or --max-extra-fields 0"
        )
    return {
        "feature_set": resolved_feature_set,
        "search_fields": requested,
        "search_field_count": len(requested),
        "search_field_status": statuses,
    }


def load_panels(args: argparse.Namespace, device: torch.device) -> tuple[dict[str, TushareGFNStockData], object, dict[str, Any]]:
    data_start = parse_date(args.data_start)
    test_end = parse_date(args.test_end)
    train_start = parse_date(args.train_start)
    valid_start = parse_date(args.valid_start)
    test_start = parse_date(args.test_start)
    if data_start > min(train_start, valid_start, test_start):
        raise ValueError("data-start must not be later than any split start")

    calendar = load_trade_dates(args.cache_root)
    frame = load_full_a_data(args.price_root, args.cap_root, data_start, test_end)
    instruments = sorted(frame["instrument"].astype(str).drop_duplicates())
    if args.universe_limit is not None:
        if args.universe_limit < 1:
            raise ValueError("universe-limit must be at least 1")
        instruments = instruments[: args.universe_limit]
    if not instruments:
        raise RuntimeError("No .SH/.SZ instruments are available in the Tushare cache")

    future_days = max(args.cycle + ALIGNMENT_LABEL_OFFSET + 1, 8)
    panels = {
        "train": build_panel(
            frame=frame,
            calendar=calendar,
            instruments=instruments,
            start=args.train_start,
            end=args.train_end,
            backtrack_days=args.backtrack_days,
            future_days=future_days,
            device=device,
            financial_root=args.financial_root,
        ),
        "valid": build_panel(
            frame=frame,
            calendar=calendar,
            instruments=instruments,
            start=args.valid_start,
            end=args.valid_end,
            backtrack_days=args.backtrack_days,
            future_days=future_days,
            device=device,
            financial_root=args.financial_root,
        ),
        "test": build_panel(
            frame=frame,
            calendar=calendar,
            instruments=instruments,
            start=args.test_start,
            end=args.test_end,
            backtrack_days=args.backtrack_days,
            future_days=future_days,
            device=device,
            financial_root=args.financial_root,
        ),
    }
    target = build_target(args.cycle)
    search_config = resolve_search_fields(
        panels["train"],
        feature_set=args.feature_set,
        extra_fields=args.extra_fields,
        max_extra_fields=args.max_extra_fields,
    )
    metadata = {
        "method": "AlphaPROBE GFlowNet",
        "method_id": "alphaprobe-gfn",
        "data_source": "Tushare cached full-A qfq Parquet",
        "price_root": str(args.price_root),
        "daily_basic_root": str(args.cap_root),
        "financial_root": str(args.financial_root),
        "alignment_rule_version": ALIGNMENT_RULE_VERSION,
        "alignment_rules_document": ALIGNMENT_RULES_DOCUMENT,
        "alignment": alignment_config_snapshot(),
        "target": f"close(t+{ALIGNMENT_LABEL_OFFSET}) -> close(t+{ALIGNMENT_LABEL_OFFSET}+{args.cycle})",
        "ic_objective": args.ic_objective,
        "cycle": args.cycle,
        "data_start": args.data_start,
        "train": {"start": args.train_start, "end": args.train_end},
        "valid": {"start": args.valid_start, "end": args.valid_end},
        "test": {"start": args.test_start, "end": args.test_end},
        "universe": "沪深全A (.SH/.SZ)",
        "universe_size": len(instruments),
        "universe_limit": args.universe_limit,
        "features": [feature.name.lower() for feature in FeatureType],
        **search_config,
        "vwap_source": panels["train"].vwap_source,
        "panels": {name: panel.summary() for name, panel in panels.items()},
        "device": str(device),
    }
    return panels, target, metadata


class NamedFieldGFNEnvCore(DiscreteEnv):
    """Local GFlowNet environment with standard and named field tokens."""

    def __init__(
        self,
        pool: AlphaPoolGFN,
        *,
        named_fields: Iterable[str] = (),
        encoder: torch.nn.Module | None = None,
        device: torch.device = torch.device("cuda:0"),
        mask_dropout_prob: float = 0.1,
        ssl_weight: float = 0.1,
        nov_weight: float = 0.1,
    ) -> None:
        self.pool = pool
        self.encoder = encoder
        self.mask_dropout_prob = mask_dropout_prob
        self.ssl_weight = ssl_weight
        self.nov_weight = nov_weight
        self.builder = GFNExpressionBuilder()
        self.named_fields = list(dict.fromkeys(str(field).lower() for field in named_fields))

        self.beg_token = [BEG_TOKEN]
        self.operators = [OperatorToken(operator) for operator in OPERATORS]
        self.features = [FeatureToken(feature) for feature in FEATURES]
        self.features.extend(NamedFieldToken(field) for field in self.named_fields)
        self.delta_times = [DeltaTimeToken(delta_time) for delta_time in DELTA_TIMES]
        self.constants = [ConstantToken(constant) for constant in CONSTANTS]
        self.sep_token = [SEP_TOKEN]
        self.action_list: list[Token] = (
            self.beg_token
            + self.operators
            + self.features
            + self.delta_times
            + self.constants
            + self.sep_token
        )
        self.id_to_token_map = {index: token for index, token in enumerate(self.action_list)}
        n_actions = len(self.action_list)
        sep_id = self.token_to_id_map[SEP_TOKEN]
        s0 = torch.tensor(
            [self.token_to_id_map[BEG_TOKEN]] + [-1] * (MAX_EXPR_LENGTH - 1),
            dtype=torch.long,
            device=device,
        )
        sf = torch.full(
            (MAX_EXPR_LENGTH,), sep_id, dtype=torch.long, device=device
        )
        preprocessor = IntegerPreprocessor(output_dim=MAX_EXPR_LENGTH)
        super().__init__(
            n_actions=n_actions,
            s0=s0,
            sf=sf,
            state_shape=(MAX_EXPR_LENGTH,),
            dummy_action=torch.tensor([-1], dtype=torch.long, device=device),
            exit_action=torch.tensor([sep_id], dtype=torch.long, device=device),
            device_str=str(device),
            preprocessor=preprocessor,
        )

    @property
    def token_to_id_map(self) -> dict[Token, int]:
        return {token: index for index, token in enumerate(self.action_list)}

    def step(self, states: DiscreteStates, actions: Actions) -> torch.Tensor:
        next_states_tensor = states.tensor.clone()
        for index, (state_tensor, action_id_tensor) in enumerate(
            zip(states.tensor, actions.tensor.squeeze(-1))
        ):
            action_id = action_id_tensor.item()
            if self.id_to_token_map[action_id] == SEP_TOKEN:
                next_states_tensor[index] = self.sf
            else:
                non_padded_len = (state_tensor != -1).sum()
                if non_padded_len < MAX_EXPR_LENGTH:
                    next_states_tensor[index, non_padded_len] = action_id
        return next_states_tensor

    def backward_step(self, states: DiscreteStates, actions: Actions) -> torch.Tensor:
        raise NotImplementedError

    def update_masks(self, states: DiscreteStates) -> None:
        batch_masks = []
        for state_tensor in states.tensor:
            if torch.all(state_tensor == self.sf):
                batch_masks.append([False] * self.n_actions)
                continue

            builder = GFNExpressionBuilder()
            token_ids = [token_id.item() for token_id in state_tensor if token_id >= 0]
            for token_id in token_ids[1:]:
                builder.add_token(self.id_to_token_map[token_id])

            valid_actions = [False] * self.n_actions
            feature_offset = len(self.beg_token) + len(self.operators)
            delta_offset = feature_offset + len(self.features)
            constant_offset = delta_offset + len(self.delta_times)

            for index, token in enumerate(self.operators):
                valid_actions[len(self.beg_token) + index] = builder.validate(token)
            for index, token in enumerate(self.features):
                valid_actions[feature_offset + index] = builder.validate(token)
            for index, token in enumerate(self.delta_times):
                valid_actions[delta_offset + index] = builder.validate(token)
            for index, token in enumerate(self.constants):
                valid_actions[constant_offset + index] = builder.validate(token)

            if len(token_ids) < MAX_EXPR_LENGTH:
                if builder.is_valid():
                    valid_actions[-1] = True
            else:
                valid_actions[-1] = True

            expr_length = len(token_ids)
            dropout = self.mask_dropout_prob * (expr_length / MAX_EXPR_LENGTH)
            true_indices = [index for index in range(len(valid_actions) - 1) if valid_actions[index]]
            if valid_actions[-1] and np.random.rand() < dropout:
                for index in true_indices:
                    valid_actions[index] = False
            batch_masks.append(valid_actions)

        states.forward_masks = torch.tensor(
            batch_masks, dtype=torch.bool, device=self.device
        )

    def reward(self, final_states: DiscreteStates) -> torch.Tensor:
        rewards = []
        for state_tensor in final_states.tensor:
            builder = GFNExpressionBuilder()
            token_ids = [token_id.item() for token_id in state_tensor if token_id >= 0]
            for token_id in token_ids[1:]:
                builder.add_token(self.id_to_token_map[token_id])

            reward = 0.0
            if builder.is_valid():
                try:
                    expression = builder.get_tree()
                    embedding = None
                    if self.encoder is not None:
                        with torch.no_grad():
                            embedding = self.encoder(state_tensor.unsqueeze(0)).squeeze(0)
                    ic_reward, nov_reward, ssl_reward = self.pool.try_new_expr_with_ssl(
                        expression, embedding
                    )
                    reward = ic_reward + self.ssl_weight * ssl_reward + self.nov_weight * nov_reward
                except OutOfDataRangeError:
                    reward = 0.0
            rewards.append(np.maximum(reward, np.exp(-10)))
        return torch.tensor(rewards, dtype=torch.float, device=self.device)


class GFNLogger:
    def __init__(self, model: torch.nn.Module, pool: AlphaPoolGFN, log_dir: Path, test_data: TushareGFNStockData, target: object):
        self.model = model
        self.pool = pool
        self.log_dir = log_dir
        self.test_data = test_data
        self.target = target
        from torch.utils.tensorboard import SummaryWriter

        self.writer = SummaryWriter(str(log_dir))
        self.target_test = self.pool._normalize_by_day(self.target.evaluate(self.test_data))

    def log_metrics(self, episode: int) -> dict[str, float | int]:
        metrics: dict[str, float | int] = {
            "episode": episode,
            "pool_size": self.pool.size,
            "eval_count": self.pool.eval_cnt,
        }
        self.writer.add_scalar("pool/size", self.pool.size, episode)
        self.writer.add_scalar("pool/eval_cnt", self.pool.eval_cnt, episode)
        if self.pool.size > 0:
            best_single_ic = float(np.max(self.pool.single_ics[: self.pool.size]))
            with torch.no_grad():
                factors = [
                    self.pool._normalize_by_day(self.pool.exprs[i].evaluate(self.test_data))
                    * self.pool.weights[i]
                    for i in range(self.pool.size)
                ]
                combined_factor = sum(factors)
                target_factor = self.target.evaluate(self.test_data)
                ic_test = batch_pearsonr(combined_factor, target_factor).mean().item()
                rank_ic_test = safe_batch_spearmanr(combined_factor, target_factor).mean().item()
            metrics.update(
                {
                    "best_single_ic": best_single_ic,
                    "test_ic": float(ic_test),
                    "test_rank_ic": float(rank_ic_test),
                }
            )
            self.writer.add_scalar("pool/best_single_ic", best_single_ic, episode)
            self.writer.add_scalar("test/ic", ic_test, episode)
            self.writer.add_scalar("test/rank_ic", rank_ic_test, episode)
        return metrics

    def save_checkpoint(self, episode: int) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        torch.save(self.model.state_dict(), self.log_dir / f"model_{episode}.pt")
        (self.log_dir / f"pool_{episode}.json").write_text(
            json.dumps(self.pool.to_dict(), ensure_ascii=False, indent=2, default=json_default) + "\n",
            encoding="utf-8",
        )

    def close(self) -> None:
        self.writer.close()


def build_gfn_components(
    args: argparse.Namespace,
    pool: AlphaPoolGFN,
    device: torch.device,
    named_fields: Iterable[str] = (),
) -> tuple[NamedFieldGFNEnvCore, torch.nn.Module, Any, Any, Any, Any, Any]:
    named_fields = list(named_fields)
    n_tokens = len(FEATURES) + len(named_fields) + len(OPERATORS) + len(DELTA_TIMES) + len(CONSTANTS)
    backbone = NamedFieldSequenceEncoder(n_tokens, args.encoder_type).to(device)
    env = NamedFieldGFNEnvCore(
        pool=pool,
        named_fields=named_fields,
        encoder=backbone,
        device=device,
        mask_dropout_prob=args.mask_dropout_prob,
        ssl_weight=args.ssl_weight,
        nov_weight=args.nov_weight,
    )
    backbone.set_action_tokens(env.id_to_token_map)
    # AlphaPROBE's original torchgfn version called this zero-layer head
    # ``NeuralNet``. In torchgfn 2.x the equivalent is a plain linear layer.
    pf_head = torch.nn.Linear(HIDDEN_DIM, env.n_actions).to(device)
    pb_head = torch.nn.Linear(HIDDEN_DIM, env.n_actions - 1).to(device)
    pf_module = torch.nn.Sequential(backbone, pf_head)
    pb_module = torch.nn.Sequential(backbone, pb_head)
    pf = DiscretePolicyEstimator(
        pf_module,
        n_actions=env.n_actions,
        preprocessor=env.preprocessor,
    )
    pb = DiscretePolicyEstimator(
        pb_module,
        n_actions=env.n_actions,
        preprocessor=env.preprocessor,
        is_backward=True,
    )
    loss_fn = EntropyTBGFlowNet(
        pf=pf,
        pb=pb,
        entropy_coef=args.entropy_coef,
        entropy_temperature=args.entropy_temperature,
    ).to(device)
    sampler = Sampler(estimator=pf)
    optimizer = torch.optim.Adam(
        list(backbone.parameters())
        + list(pf_head.parameters())
        + list(pb_head.parameters())
        + [loss_fn.logZ],
        lr=args.learning_rate,
    )
    return env, backbone, pf, pb, loss_fn, sampler, optimizer


def dry_run(args: argparse.Namespace, panels: dict[str, TushareGFNStockData], target: object, metadata: dict[str, Any], device: torch.device) -> None:
    train_data = panels["train"]
    pool = ObjectiveAlphaPoolGFN(
        capacity=args.pool_capacity,
        stock_data=train_data,
        target=target,
        ic_objective=args.ic_objective,
    )
    env, *_ = build_gfn_components(args, pool, device, metadata.get("search_fields", []))
    target_values = target.evaluate(train_data)
    finite = int(torch.isfinite(target_values).sum().item())
    print(json.dumps({
        "status": "dry-run-ok",
        "metadata": metadata,
        "target_shape": list(target_values.shape),
        "target_finite_values": finite,
        "gfn_actions": env.n_actions,
        "pool_capacity": args.pool_capacity,
        "encoder_type": args.encoder_type,
    }, ensure_ascii=False, indent=2, default=json_default))


def prepare_output(path: Path, overwrite: bool) -> None:
    path = path.expanduser().resolve()
    if path.exists() and any(path.iterdir()) and not overwrite:
        raise FileExistsError(
            f"Output directory is not empty: {path}; choose another --output or pass --overwrite"
        )
    path.mkdir(parents=True, exist_ok=True)


def train(args: argparse.Namespace, panels: dict[str, TushareGFNStockData], target: object, metadata: dict[str, Any], device: torch.device) -> None:
    output = args.output.expanduser().resolve()
    prepare_output(output, args.overwrite)
    (output / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )

    train_data = panels["train"]
    pool = ObjectiveAlphaPoolGFN(
        capacity=args.pool_capacity,
        stock_data=train_data,
        target=target,
        ic_mut_threshold=args.ic_mut_threshold,
        ic_objective=args.ic_objective,
    )
    env, backbone, _, _, loss_fn, sampler, optimizer = build_gfn_components(
        args, pool, device, metadata.get("search_fields", [])
    )
    logger = GFNLogger(backbone, pool, output / "checkpoints", panels["test"], target)
    losses: list[float] = []
    metrics: list[dict[str, float | int]] = []
    minibatch_loss: torch.Tensor | int = 0

    try:
        for episode in range(args.n_episodes):
            env.ssl_weight = args.ssl_weight * args.weight_schedule(episode, args.n_episodes)
            env.nov_weight = args.nov_weight * args.weight_schedule(episode, args.n_episodes)
            trajectories = sampler.sample_trajectories(
                env=env,
                n_trajectories=args.trajectories_per_episode,
                save_estimator_outputs=args.entropy_coef > 0,
            )
            loss = loss_fn.loss(env=env, trajectories=trajectories)
            if loss is not None and torch.isfinite(loss):
                minibatch_loss = minibatch_loss + loss

            if (episode + 1) % args.update_freq == 0 and isinstance(minibatch_loss, torch.Tensor):
                losses.append(float(minibatch_loss.detach().item()))
                minibatch_loss.backward()
                optimizer.step()
                optimizer.zero_grad()
                minibatch_loss = 0

            if (episode + 1) % args.log_freq == 0:
                current = logger.log_metrics(episode + 1)
                current["loss"] = losses[-1] if losses else float("nan")
                metrics.append(current)
                logger.save_checkpoint(episode + 1)
                print(json.dumps(current, ensure_ascii=False, default=json_default))
    finally:
        logger.close()

    (output / "training_history.json").write_text(
        json.dumps({"losses": losses, "metrics": metrics}, ensure_ascii=False, indent=2, default=json_default)
        + "\n",
        encoding="utf-8",
    )
    (output / "final_pool.json").write_text(
        json.dumps(pool.to_dict(), ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="load Tushare data and initialize GFlowNet only")
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--price-root", type=Path, default=DEFAULT_PRICE_ROOT)
    parser.add_argument("--cap-root", type=Path, default=DEFAULT_CAP_ROOT)
    parser.add_argument(
        "--financial-root",
        type=Path,
        default=DEFAULT_FINANCIAL_ROOT,
        help="PIT Tushare financial cache used by named statement and valuation fields",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--data-start", default=ALIGNMENT_DATA_START)
    parser.add_argument("--train-start", default="20210907")
    parser.add_argument("--train-end", default="20240906")
    parser.add_argument("--valid-start", default="20240909")
    parser.add_argument("--valid-end", default="20250905")
    parser.add_argument("--test-start", default="20250908")
    parser.add_argument("--test-end", default=ALIGNMENT_END)
    parser.add_argument("--cycle", type=int, default=5)
    parser.add_argument(
        "--ic-objective",
        choices=sorted(ObjectiveAlphaPoolGFN.VALID_OBJECTIVES),
        default="signed_positive",
        help="single-factor IC objective; signed_positive rejects non-positive IC candidates",
    )
    parser.add_argument(
        "--feature-set",
        choices=["price_volume", "fundamental_core", "all_active"],
        default="price_volume",
        help="named-field action space; fundamental_core is the controlled finance set",
    )
    parser.add_argument(
        "--extra-fields",
        type=str,
        default=None,
        help="comma-separated named fields or a newline-separated field file; overrides feature-set",
    )
    parser.add_argument(
        "--max-extra-fields",
        type=int,
        default=64,
        help="guard for named fields; 0 disables the guard",
    )
    parser.add_argument(
        "--backtrack-days",
        type=int,
        default=512,
        help="trading-day warmup; 512 covers nested 50-day operators in MAX_EXPR_LENGTH=20",
    )
    parser.add_argument("--universe-limit", type=int)
    parser.add_argument("--pool-capacity", type=int, default=50)
    parser.add_argument("--n-episodes", type=int, default=10_000)
    parser.add_argument("--trajectories-per-episode", type=int, default=1)
    parser.add_argument("--log-freq", type=int, default=1000)
    parser.add_argument("--update-freq", type=int, default=128)
    parser.add_argument("--encoder-type", choices=["transformer", "lstm", "gnn"], default="transformer")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--entropy-coef", type=float, default=0.01)
    parser.add_argument("--entropy-temperature", type=float, default=1.0)
    parser.add_argument("--mask-dropout-prob", type=float, default=1.0)
    parser.add_argument("--ssl-weight", type=float, default=1.0)
    parser.add_argument("--nov-weight", type=float, default=0.3)
    parser.add_argument("--final-weight-ratio", type=float, default=0.0)
    parser.add_argument("--ic-mut-threshold", type=float, default=0.3)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.cycle < 1 or args.pool_capacity < 1 or args.n_episodes < 1:
        raise ValueError("cycle, pool-capacity and n-episodes must be positive")
    if not 0 <= args.final_weight_ratio <= 1:
        raise ValueError("final-weight-ratio must be between 0 and 1")

    validate_alignment_config(alignment_config_snapshot())
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = resolve_device(args.device)
    args.cache_root = args.cache_root.expanduser().resolve()
    args.price_root = args.price_root.expanduser().resolve()
    args.cap_root = args.cap_root.expanduser().resolve()
    args.financial_root = args.financial_root.expanduser().resolve()

    def weight_schedule(episode: int, total: int) -> float:
        progress = min(max((episode + 1) / max(total, 1), 0.0), 1.0)
        return 1.0 - progress * (1.0 - args.final_weight_ratio)

    args.weight_schedule = weight_schedule
    panels, target, metadata = load_panels(args, device)
    if args.dry_run:
        dry_run(args, panels, target, metadata, device)
        return 0
    train(args, panels, target, metadata, device)
    print(f"GFlowNet training completed; outputs: {args.output.expanduser().resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
