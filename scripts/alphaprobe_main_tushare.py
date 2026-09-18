#!/usr/bin/env python3
"""Run AlphaPROBE's paper-mainline search on the local Tushare panel.

The paper-mainline method is a Bayesian/ICIR retriever over an expression DAG
followed by an LLM factor generator.  This adapter keeps that search shape but
uses the project's aligned Tushare panel, label-1 target, and net-excess
diagnostic.  It deliberately does not import AlphaPROBE's Qlib trainer: that
trainer hard-codes a 20-day label, Qlib data, the default expression parser,
and a remote OpenAI client.

The local Ollama generator is used by default.  Embedding-based semantic
similarity is disabled when the Qwen embedding model is unavailable; ICIR,
depth, repeat count, expression lineage, and cross-sectional redundancy remain
active retriever terms and the run metadata records this limitation.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

import numpy as np
import pandas as pd
import torch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALPHAPROBE_SRC = PROJECT_ROOT / "quantlab" / "third_party" / "AlphaPROBE" / "src"
if str(ALPHAPROBE_SRC) not in sys.path:
    sys.path.insert(0, str(ALPHAPROBE_SRC))
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from alphagen.data.expression import (  # noqa: E402
    Abs,
    Add,
    BinaryOperator,
    Constant,
    Div,
    Expression,
    Feature,
    GetGreater,
    GetLess,
    Greater,
    Inv,
    Less,
    Log,
    Mul,
    PairRollingOperator,
    Pow,
    Rank,
    Ref,
    RollingOperator,
    SLog1p,
    Sign,
    Sub,
    TsCov,
    TsCorr,
    TsDelta,
    TsDiv,
    TsEMA,
    TsIr,
    TsKurt,
    TsMad,
    TsMax,
    TsMaxDiff,
    TsMean,
    TsMed,
    TsMin,
    TsMinDiff,
    TsMinMaxDiff,
    TsPctChange,
    TsRank,
    TsSkew,
    TsStd,
    TsSum,
    TsVar,
    TsWMA,
)
from alphagen.data.expression_knowledge_graph import (  # noqa: E402
    ExpressionKnowledgeGraph,
    ExpressionNode,
    ExpressionPayload,
)
from alphagen.data.tokens import (  # noqa: E402
    ConstantToken,
    DeltaTimeToken,
    FeatureToken,
    OperatorToken,
    Token,
)
from alphagen.data.tree import ExpressionBuilder, InvalidExpressionException, OutOfDataRangeError  # noqa: E402
from alphagen.models.alpha_pool import AlphaPool  # noqa: E402
from alphagen_qlib.stock_data import FeatureType  # noqa: E402
from alphagen.utils.correlation import batch_pearsonr  # noqa: E402
from alphaprobe_gp_tushare import (  # noqa: E402
    AlignedNetExcessContext,
    TushareStockData,
    load_trade_dates,
)
from full_a_local_data import load_full_a_data  # noqa: E402
from pandaai_fields_local import PandaAIField  # noqa: E402
from platform_alignment_rules import (  # noqa: E402
    ALIGNMENT_DATA_START,
    ALIGNMENT_END,
    ALIGNMENT_GROUPS,
    ALIGNMENT_LABEL_OFFSET,
    ALIGNMENT_ROUND_TRIP_COST,
    ALIGNMENT_RULES_DOCUMENT,
    ALIGNMENT_RULE_VERSION,
    alignment_config_snapshot,
    validate_alignment_config,
)
from search_field_policy import resolve_named_search_fields  # noqa: E402


DEFAULT_CACHE_ROOT = PROJECT_ROOT / "quantlab" / ".quantlab" / "cache" / "research" / "cn_equity"
DEFAULT_PRICE_ROOT = DEFAULT_CACHE_ROOT / "tushare_factor_recheck" / "qfq" / "daily_batches"
DEFAULT_CAP_ROOT = DEFAULT_CACHE_ROOT / "tushare_factor_recheck" / "daily_basic_full_a"
DEFAULT_FINANCIAL_ROOT = DEFAULT_CACHE_ROOT / "financial_full_a"
DEFAULT_OUTPUT = PROJECT_ROOT / "research_reports" / "alphaprobe_main_tushare_20260918"

BASE_FEATURE_NAMES = {feature.name.lower() for feature in FeatureType}
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
OPERATOR_TYPES = (
    Abs,
    SLog1p,
    Inv,
    Sign,
    Log,
    Rank,
    Add,
    Sub,
    Mul,
    Div,
    Pow,
    Greater,
    Less,
    GetGreater,
    GetLess,
    Ref,
    TsMean,
    TsSum,
    TsStd,
    TsIr,
    TsMinMaxDiff,
    TsMaxDiff,
    TsMinDiff,
    TsVar,
    TsSkew,
    TsKurt,
    TsMax,
    TsMin,
    TsMed,
    TsMad,
    TsRank,
    TsDelta,
    TsDiv,
    TsPctChange,
    TsWMA,
    TsEMA,
    TsCov,
    TsCorr,
)
OPERATOR_MAP = {operator.__name__: operator for operator in OPERATOR_TYPES}
OPERATOR_NAMES = ", ".join(operator.__name__ for operator in OPERATOR_TYPES)
NUMBER_PATTERN = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
FIELD_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


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
    if isinstance(value, (pd.Timestamp,)):
        return date_text(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().tolist()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def clean_tensor(value: torch.Tensor) -> torch.Tensor:
    """Make inf values explicit missing values before AlphaPROBE normalization."""
    return torch.where(torch.isfinite(value), value, torch.full_like(value, torch.nan))


def scaled_net_excess(net_excess: float | None, weight: float, scale: float) -> float:
    if net_excess is None or not np.isfinite(net_excess):
        return 0.0
    return float(weight * math.tanh(float(net_excess) / scale))


class LocalNamedField(PandaAIField):
    """Named Tushare/PandaAI leaf used by the local parser and DAG."""

    def __str__(self) -> str:
        return f"${self.field_name}"


class NamedFieldToken(Token):
    def __init__(self, field_name: str) -> None:
        normalized = str(field_name).strip().lower()
        if FIELD_PATTERN.fullmatch(normalized) is None:
            raise ValueError(f"Invalid named field: {field_name}")
        self.field_name = normalized

    def __str__(self) -> str:
        return f"${self.field_name}"


class LocalExpressionBuilder(ExpressionBuilder):
    def add_token(self, token: Token) -> None:
        if isinstance(token, NamedFieldToken):
            if not self.validate(token):
                raise InvalidExpressionException(
                    f"Token {token} not allowed here, stack: {self.stack}."
                )
            self.stack.append(LocalNamedField(token.field_name))
            return
        super().add_token(token)

    def validate(self, token: Token) -> bool:
        if isinstance(token, NamedFieldToken):
            return self.validate_feature()
        return super().validate(token)


class LocalExpressionParser:
    """AlphaPROBE parser extended with local named fields."""

    def __init__(self, named_fields: Iterable[str]) -> None:
        self.named_fields = {
            str(field).strip().lower()
            for field in named_fields
            if FIELD_PATTERN.fullmatch(str(field).strip().lower())
        }

    @staticmethod
    def _split_arguments(value: str) -> list[str]:
        arguments: list[str] = []
        current: list[str] = []
        depth = 0
        for char in value:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            if char == "," and depth == 0:
                arguments.append("".join(current).strip())
                current = []
            else:
                current.append(char)
        tail = "".join(current).strip()
        if tail:
            arguments.append(tail)
        return arguments

    def tokenize(self, expression: str) -> list[Token]:
        tokens: list[Token] = []
        feature_map = {f"${feature.name.lower()}": feature for feature in FeatureType}

        def parse_one(value: str) -> None:
            value = value.strip()
            lowered = value.lower()
            if lowered in feature_map:
                tokens.append(FeatureToken(feature_map[lowered]))
                return
            field_name = lowered[1:] if lowered.startswith("$") else lowered
            if field_name in self.named_fields:
                tokens.append(NamedFieldToken(field_name))
                return
            if NUMBER_PATTERN.fullmatch(value):
                number = float(value)
                if re.fullmatch(r"[+-]?\d+", value):
                    tokens.append(DeltaTimeToken(int(number)))
                else:
                    tokens.append(ConstantToken(number))
                return
            if "(" in value and value.endswith(")"):
                operator_name = value[: value.find("(")].strip()
                operator = OPERATOR_MAP.get(operator_name)
                if operator is None:
                    raise ValueError(f"Unknown operator: {operator_name}")
                inner = value[value.find("(") + 1 : value.rfind(")")]
                arguments = self._split_arguments(inner)
                if len(arguments) != operator.n_args():
                    raise ValueError(
                        f"{operator_name} expects {operator.n_args()} arguments, got {len(arguments)}"
                    )
                for argument in arguments:
                    parse_one(argument)
                tokens.append(OperatorToken(operator))
                return
            raise ValueError(f"Invalid expression: {value}")

        parse_one(expression)
        return tokens

    def parse(self, expression: str) -> Expression:
        builder = LocalExpressionBuilder()
        for token in self.tokenize(expression):
            builder.add_token(token)
        return builder.get_tree()


class LocalKnowledgeGraph(ExpressionKnowledgeGraph):
    """ExpressionKnowledgeGraph with named-field payloads and working lookup."""

    def __init__(self, parser: LocalExpressionParser, depth_limit: int, expression_size_limit: int) -> None:
        super().__init__(depth_limit=depth_limit, expression_size_limit=expression_size_limit)
        self._parser = parser

    def _build_payload(self, expression: str) -> Optional[ExpressionPayload]:
        try:
            source = expression.strip()
            expression_object = self._parser.parse(source.replace("%d", "10"))
        except (InvalidExpressionException, ValueError) as exc:
            print(f"[DAG reject parse] {expression}: {exc}")
            return None
        tokens = self._tokenize_local(expression_object)
        return ExpressionPayload(
            expression=expression_object,
            length=len(tokens),
            tokens=tokens,
            source=source,
        )

    def _tokenize_local(self, expression: Expression) -> tuple[str, ...]:
        if isinstance(expression, LocalNamedField):
            return (f"FIELD:{expression.field_name}",)
        if isinstance(expression, Feature):
            return (f"FEATURE:{expression._feature.name}",)
        if isinstance(expression, Constant):
            return (f"CONST:{self._format_constant(expression._value)}",)
        if isinstance(expression, (Abs, SLog1p, Inv, Sign, Log, Rank)):
            return (f"OP:{type(expression).__name__}",) + self._tokenize_local(expression._operand)
        if isinstance(expression, (Add, Sub, Mul, Div, Pow, Greater, Less, GetGreater, GetLess)):
            return (
                f"OP:{type(expression).__name__}",
            ) + self._tokenize_local(expression._lhs) + self._tokenize_local(expression._rhs)
        if isinstance(expression, RollingOperator):
            return (
                f"OP:{type(expression).__name__}",
                f"DT:{expression._delta_time}",
            ) + self._tokenize_local(expression._operand)
        if isinstance(expression, PairRollingOperator):
            return (
                f"OP:{type(expression).__name__}",
                f"DT:{expression._delta_time}",
            ) + self._tokenize_local(expression._lhs) + self._tokenize_local(expression._rhs)
        raise TypeError(f"Unsupported expression type for tokenization: {type(expression).__name__}")

    def insert(self, expression_node: ExpressionNode, parent_node: Optional[ExpressionNode]) -> bool:
        source = expression_node.payload.source.strip()
        if self.search(source) is not None:
            return False
        if parent_node is not None:
            expression_node.parent = parent_node
            expression_node.depth = parent_node.depth + 1
            if expression_node.depth > self._depth_limit:
                return False
            parent_node.children.add(source)
        self._nodes[source] = expression_node
        self._node_records[source] = expression_node
        self._size += 1
        return True


class MainlineAlphaPool(AlphaPool):
    """AlphaPool with signed-IC admission and the paper's DAG retriever terms."""

    def __init__(
        self,
        capacity: int,
        stock_data: TushareStockData,
        target: Expression,
        *,
        graph: LocalKnowledgeGraph,
        net_context: AlignedNetExcessContext,
        ic_mut_threshold: float,
        top_k: int,
        depth_decay: float,
        times_decay: float,
        net_excess_weight: float,
        net_excess_scale: float,
        max_size_corr: float | None,
    ) -> None:
        super().__init__(capacity, stock_data, target)
        self.graph = graph
        self.net_context = net_context
        self.ic_mut_threshold = float(ic_mut_threshold)
        self.top_k = int(top_k)
        self.depth_decay = float(depth_decay)
        self.times_decay = float(times_decay)
        self.net_excess_weight = float(net_excess_weight)
        self.net_excess_scale = float(net_excess_scale)
        self.max_size_corr = None if max_size_corr is None else float(max_size_corr)
        self._market_cap: Optional[torch.Tensor] = None
        self.topics: list[Optional[str]] = [None] * (capacity + 1)
        self.descriptions: list[Optional[str]] = [None] * (capacity + 1)
        self.expr2node: list[Optional[ExpressionNode]] = [None] * (capacity + 1)
        self.icir: np.ndarray = np.zeros(capacity + 1, dtype=float)
        self.net_excess: np.ndarray = np.full(capacity + 1, np.nan, dtype=float)
        self.size_corr: np.ndarray = np.full(capacity + 1, np.nan, dtype=float)
        self.objective_scores: np.ndarray = np.zeros(capacity + 1, dtype=float)

    def _size_exposure(self, value: torch.Tensor) -> float | None:
        if self._market_cap is None:
            self._market_cap = clean_tensor(self.data.get_named_feature("market_cap"))
        daily_corr = batch_spearman_linear(value, self._market_cap)
        daily_corr = daily_corr[torch.isfinite(daily_corr)]
        if daily_corr.numel() == 0:
            return None
        return float(daily_corr.abs().mean().item())

    def _daily_metrics(self, value: torch.Tensor) -> dict[str, float | None]:
        normalized = self._normalize_by_day(clean_tensor(value))
        target = clean_tensor(self.target)
        daily_ic = batch_pearsonr(normalized, target)
        rank_ic = batch_spearman_linear(normalized, target)
        daily_ic = daily_ic[torch.isfinite(daily_ic)]
        rank_ic = rank_ic[torch.isfinite(rank_ic)]
        if daily_ic.numel() == 0:
            return {"ic": None, "icir": None, "rank_ic": None, "periods": 0}
        ic = float(daily_ic.mean().item())
        std = float(daily_ic.std(unbiased=False).item())
        return {
            "ic": ic,
            "icir": ic / (std + 1e-6),
            "rank_ic": float(rank_ic.mean().item()) if rank_ic.numel() else None,
            "periods": int(daily_ic.numel()),
        }

    def score_expression(self, expression: Expression) -> dict[str, Any]:
        raw = clean_tensor(expression.evaluate(self.data))
        normalized = self._normalize_by_day(raw)
        metrics = self._daily_metrics(raw)
        mutual: list[float] = []
        for index in range(self.size):
            mutual_value = float(batch_pearsonr(normalized, self.values[index]).mean().item())  # type: ignore[arg-type]
            mutual.append(mutual_value)
        net_stats = self.net_context.score(raw)
        net = net_stats.get("net_excess")
        net_value = float(net) if net is not None and np.isfinite(net) else None
        size_corr = self._size_exposure(raw)
        ic = metrics.get("ic")
        objective = float(ic) if ic is not None else -1.0
        objective += scaled_net_excess(net_value, self.net_excess_weight, self.net_excess_scale)
        return {
            "raw": raw,
            "normalized": normalized,
            "ic": ic,
            "icir": metrics.get("icir"),
            "rank_ic": metrics.get("rank_ic"),
            "periods": metrics.get("periods"),
            "mutual_ics": mutual,
            "max_mutual_ic": max((abs(item) for item in mutual), default=0.0),
            "size_corr": size_corr,
            "objective": objective,
            "net": net_stats,
        }

    def _add_factor_with_metadata(
        self,
        expression: Expression,
        scored: dict[str, Any],
        topic: str,
        description: str,
        node: ExpressionNode,
    ) -> None:
        super()._add_factor(
            expression,
            scored["normalized"],
            float(scored["ic"]),
            [abs(float(value)) for value in scored["mutual_ics"]],
        )
        index = self.size - 1
        self.topics[index] = topic
        self.descriptions[index] = description
        self.expr2node[index] = node
        self.icir[index] = float(scored["icir"] or 0.0)
        self.net_excess[index] = float(scored["net"].get("net_excess")) if scored["net"].get("net_excess") is not None else np.nan
        self.size_corr[index] = float(scored["size_corr"]) if scored.get("size_corr") is not None else np.nan
        self.objective_scores[index] = float(scored["objective"])
        self.weights[index] = float(scored["ic"])

    def register_expression_node(self, node: ExpressionNode) -> None:
        for index in range(self.size):
            if self.exprs[index] is not None and str(self.exprs[index]) == node.payload.expression.__str__():
                self.expr2node[index] = node
                return

    def try_new_expr(
        self,
        expression: Expression,
        topic: str,
        description: str,
        node: ExpressionNode,
        scored: Optional[dict[str, Any]] = None,
    ) -> bool:
        if any(self.exprs[index] is not None and str(self.exprs[index]) == str(expression) for index in range(self.size)):
            return False
        scored = self.score_expression(expression) if scored is None else scored
        ic = scored.get("ic")
        if ic is None or float(ic) <= 0.0:
            return False
        size_corr = scored.get("size_corr")
        if (
            self.max_size_corr is not None
            and size_corr is not None
            and float(size_corr) > self.max_size_corr
        ):
            return False
        if float(scored["max_mutual_ic"]) > self.ic_mut_threshold:
            return False
        if self.size >= self.capacity and float(scored["objective"]) <= float(np.min(self.objective_scores[: self.size])):
            return False
        self._add_factor_with_metadata(expression, scored, topic, description, node)
        self.eval_cnt += 1
        self._pop_by_objective()
        return True

    def _swap_idx(self, first: int, second: int) -> None:
        if first == second:
            return
        super()._swap_idx(first, second)
        self.topics[first], self.topics[second] = self.topics[second], self.topics[first]
        self.descriptions[first], self.descriptions[second] = self.descriptions[second], self.descriptions[first]
        self.expr2node[first], self.expr2node[second] = self.expr2node[second], self.expr2node[first]
        self.icir[first], self.icir[second] = self.icir[second], self.icir[first]
        self.net_excess[first], self.net_excess[second] = self.net_excess[second], self.net_excess[first]
        self.size_corr[first], self.size_corr[second] = self.size_corr[second], self.size_corr[first]
        self.objective_scores[first], self.objective_scores[second] = self.objective_scores[second], self.objective_scores[first]

    def _pop_by_objective(self) -> None:
        if self.size <= self.capacity:
            return
        worst = int(np.argmin(self.objective_scores[: self.size]))
        self._swap_idx(worst, self.capacity)
        self.size = self.capacity

    def search(self) -> tuple[list[ExpressionNode], list[Expression]]:
        pairs = [
            (index, self.expr2node[index])
            for index in range(self.size)
            if self.exprs[index] is not None and self.expr2node[index] is not None
        ]
        if not pairs:
            return [], []
        indices = [item[0] for item in pairs]
        nodes = [item[1] for item in pairs]
        icir = np.asarray([self.icir[index] for index in indices], dtype=float)
        standardized = (icir - icir.mean()) / (icir.std() + 1e-6)
        posterior = 1.0 / (1.0 + np.exp(-standardized))
        depths = np.asarray([node.depth for node in nodes], dtype=float)
        times = np.asarray([node.times for node in nodes], dtype=float)
        prior = np.power(max(1.0 - self.depth_decay, 1e-6), depths)
        repeat_penalty = np.power(max(1.0 - self.times_decay, 1e-6), np.maximum(times - 2.0, 0.0))
        corr = np.abs(self.mutual_ics[np.ix_(indices, indices)])
        np.fill_diagonal(corr, 0.0)
        redundancy = 1.0 - corr.mean(axis=1)
        dag_gain = np.ones(len(nodes), dtype=float)
        for position, node in enumerate(nodes):
            if not node.children:
                continue
            child_icirs: list[float] = []
            for child_source in node.children:
                child_node = self.graph.search(child_source)
                if child_node is not None:
                    child_icirs.append(float(child_node.icir))
            if child_icirs:
                parent_icir = float(icir[position])
                gains = np.asarray(child_icirs, dtype=float) - parent_icir
                gains = gains / (abs(parent_icir) + 1e-6)
                dag_gain[position] = float(np.mean(1.0 / (1.0 + np.exp(-gains))))
        scores = posterior * prior * repeat_penalty * dag_gain * np.clip(redundancy, 1e-6, 1.0)

        leaf = [position for position, node in enumerate(nodes) if not node.children]
        non_leaf = [position for position, node in enumerate(nodes) if node.children]
        half = max(1, self.top_k // 2)
        selected = sorted(leaf, key=lambda position: scores[position], reverse=True)[:half]
        selected += sorted(non_leaf, key=lambda position: scores[position], reverse=True)[:half]
        if len(selected) < self.top_k:
            remaining = [position for position in np.argsort(-scores) if int(position) not in selected]
            selected += remaining[: self.top_k - len(selected)]
        selected = selected[: self.top_k]
        selected.sort(key=lambda position: scores[position], reverse=True)
        for position in selected:
            nodes[position].times += 1
        return [nodes[position] for position in selected], [self.exprs[indices[position]] for position in selected]  # type: ignore[list-item]

    def to_dict(self) -> dict[str, Any]:
        factors = []
        for index in range(self.size):
            factors.append(
                {
                    "expression": str(self.exprs[index]),
                    "topic": self.topics[index],
                    "description": self.descriptions[index],
                    "ic": float(self.single_ics[index]),
                    "icir": float(self.icir[index]),
                    "rank": float(self.objective_scores[index]),
                    "net_excess": None if not np.isfinite(self.net_excess[index]) else float(self.net_excess[index]),
                    "size_corr": None if not np.isfinite(self.size_corr[index]) else float(self.size_corr[index]),
                    "node": self.expr2node[index].as_dict() if self.expr2node[index] is not None else None,
                }
            )
        return {"capacity": self.capacity, "size": self.size, "factors": factors}


def _average_rank(value: torch.Tensor, valid: torch.Tensor) -> torch.Tensor:
    safe = torch.where(valid, value, torch.full_like(value, torch.inf))
    order = torch.argsort(safe, dim=1, stable=True)
    sorted_value = safe.gather(1, order)
    sorted_valid = valid.gather(1, order)
    previous = torch.cat([torch.full_like(sorted_value[:, :1], torch.inf), sorted_value[:, :-1]], dim=1)
    previous_valid = torch.cat([torch.zeros_like(sorted_valid[:, :1]), sorted_valid[:, :-1]], dim=1)
    starts = sorted_valid & (~previous_valid | (sorted_value != previous))
    group = starts.to(dtype=torch.long).cumsum(dim=1) - 1
    group = group.clamp_min(0)
    positions = torch.arange(value.shape[1], device=value.device, dtype=torch.float32).expand_as(safe)
    valid_float = sorted_valid.to(dtype=torch.float32)
    sums = torch.zeros_like(safe).scatter_add(1, group, positions * valid_float)
    counts = torch.zeros_like(safe).scatter_add(1, group, valid_float)
    ranks_sorted = sums.gather(1, group) / counts.gather(1, group).clamp_min(1.0)
    ranks = torch.empty_like(safe).scatter(1, order, ranks_sorted)
    return ranks.masked_fill(~valid, torch.nan)


def batch_spearman_linear(x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
    valid = torch.isfinite(x) & torch.isfinite(y)
    return batch_pearsonr(_average_rank(x, valid), _average_rank(y, valid))


def build_target(cycle: int) -> Expression:
    close = Feature(FeatureType.CLOSE)
    entry = Ref(close, -ALIGNMENT_LABEL_OFFSET)
    exit_ = Ref(close, -(ALIGNMENT_LABEL_OFFSET + cycle))
    return exit_ / entry - 1


def build_panel(
    frame: pd.DataFrame,
    calendar: Sequence[pd.Timestamp],
    instruments: Sequence[str],
    start: str,
    end: str,
    args: argparse.Namespace,
    device: torch.device,
) -> TushareStockData:
    return TushareStockData.from_aligned_frame(
        frame=frame,
        calendar=calendar,
        instrument=instruments,
        start_time=start,
        end_time=end,
        max_backtrack_days=args.backtrack_days,
        max_future_days=max(args.cycle + ALIGNMENT_LABEL_OFFSET + 2, 8),
        device=device,
        financial_root=args.financial_root,
    )


def load_panels(args: argparse.Namespace, device: torch.device) -> tuple[dict[str, TushareStockData], Expression, dict[str, Any]]:
    data_start = parse_date(args.data_start)
    test_end = parse_date(args.test_end)
    calendar = load_trade_dates(args.cache_root)
    frame = load_full_a_data(args.price_root, args.cap_root, data_start, test_end)
    instruments = sorted(frame["instrument"].astype(str).drop_duplicates())
    if args.universe_limit is not None:
        if args.universe_limit < 1:
            raise ValueError("--universe-limit must be positive")
        instruments = instruments[: args.universe_limit]
    if not instruments:
        raise RuntimeError("No .SH/.SZ instruments are available")
    panels = {
        "train": build_panel(frame, calendar, instruments, args.train_start, args.train_end, args, device),
        "valid": build_panel(frame, calendar, instruments, args.valid_start, args.valid_end, args, device),
        "test": build_panel(frame, calendar, instruments, args.test_start, args.test_end, args, device),
    }
    search_config = resolve_named_search_fields(
        panels["train"],
        feature_set=args.feature_set,
        extra_fields=args.extra_fields,
        max_extra_fields=args.max_extra_fields,
        allow_unverified_fields=args.allow_unverified_fields,
        base_feature_names=BASE_FEATURE_NAMES,
        fundamental_core_fields=FUNDAMENTAL_CORE_FIELDS,
        allow_blocked_fields=args.allow_blocked_fields,
    )
    target = build_target(args.cycle)
    metadata = {
        "method": "AlphaPROBE Bayesian factor retriever + DAG-aware factor generator",
        "method_id": "alphaprobe-mainline-tushare",
        "paper_mainline": {
            "retriever": "ICIR posterior + depth prior + repeat penalty + mutual-correlation redundancy",
            "generator": "DAG lineage-conditioned Ollama Qwen3",
            "semantic_embedding": "disabled_no_local_embedding_model",
            "source_code": [
                "quantlab/third_party/AlphaPROBE/src/alpha_knowledge/alpha_pool.py",
                "quantlab/third_party/AlphaPROBE/src/alphagen/data/expression_knowledge_graph.py",
            ],
        },
        "data_source": "Tushare cached full-A qfq Parquet",
        "alignment_rule_version": ALIGNMENT_RULE_VERSION,
        "alignment_rules_document": ALIGNMENT_RULES_DOCUMENT,
        "alignment": alignment_config_snapshot(),
        "target": f"close(t+{ALIGNMENT_LABEL_OFFSET}) -> close(t+{ALIGNMENT_LABEL_OFFSET}+{args.cycle})",
        "cycle": args.cycle,
        "data_start": args.data_start,
        "train": {"start": args.train_start, "end": args.train_end},
        "valid": {"start": args.valid_start, "end": args.valid_end},
        "test": {"start": args.test_start, "end": args.test_end},
        "universe": "沪深全A (.SH/.SZ)" if args.universe_limit is None else "smoke subset of 沪深全A",
        "universe_size": len(instruments),
        "universe_limit": args.universe_limit,
        "feature_search": search_config,
        "net_excess_reward": {
            "train_only": True,
            "weight": args.net_excess_weight,
            "scale": args.net_excess_scale,
            "groups": ALIGNMENT_GROUPS,
            "round_trip_cost": ALIGNMENT_ROUND_TRIP_COST,
            "benchmark_mode": alignment_config_snapshot()["benchmark_mode"],
        },
        "size_neutrality": {
            "reference_field": "market_cap",
            "metric": "mean_absolute_daily_cross_sectional_spearman",
            "max_allowed": args.max_size_corr,
            "search_excludes_size_and_valuation_fields": args.max_size_corr is not None,
        },
        "generator": {
            "provider": args.generator,
            "model": args.model,
            "temperature": args.temperature,
            "generate_num": args.generate_num,
        },
        "panels": {name: panel.summary() for name, panel in panels.items()},
        "device": str(device),
    }
    return panels, target, metadata


class OllamaGenerator:
    def __init__(self, args: argparse.Namespace, named_fields: Sequence[str]) -> None:
        self.provider = args.generator
        self.endpoint = args.ollama_url.rstrip("/") + "/api/chat"
        self.model = args.model
        self.temperature = args.temperature
        self.num_predict = args.num_predict
        self.named_fields = list(named_fields)

    def _fallback(self, parent: str) -> list[dict[str, str]]:
        candidates = [
            ("TsRank($close, %d)", "time-series position of close over a recent window"),
            ("Div(TsMean($close, %d), $close)", "distance of current close from its rolling mean"),
            ("Div(TsStd($close, %d), $close)", "rolling relative price volatility"),
            ("Div(TsMean($volume, %d), Add($volume, 0.000001))", "recent volume compression or expansion"),
        ]
        if self.named_fields:
            field = self.named_fields[0]
            candidates.append((f"Rank(${field})", f"cross-sectional rank of {field}"))
        return [{"expression": expression, "explanation": explanation} for expression, explanation in candidates]

    @staticmethod
    def _extract_json(content: str) -> dict[str, Any] | None:
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL | re.IGNORECASE).strip()
        try:
            parsed = json.loads(content)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            pass
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(content[start : end + 1])
                return parsed if isinstance(parsed, dict) else None
            except json.JSONDecodeError:
                return None
        return None

    def generate(self, node: ExpressionNode, trace: str, number: int) -> tuple[list[dict[str, str]], str]:
        if self.provider == "fallback":
            return self._fallback(node.payload.source)[:number], "fallback"
        leaves = ["$open", "$close", "$high", "$low", "$volume"]
        leaves.extend(f"${field}" for field in self.named_fields)
        prompt = f"""You are the factor generator in a quantitative factor-research pipeline.
Return only a JSON object with an `expressions` list and an `explanations` list.
Generate exactly {number} distinct, dimensionless expressions.
The parent expression is: {node.payload.source}
Topic: {node.topic or 'cross-sectional equity alpha'}
Parent explanation: {node.description or ''}
DAG lineage from root: {trace or node.payload.source}
Allowed leaves: {', '.join(leaves)}
Allowed operators: {OPERATOR_NAMES}
Use integer `%d` as the window in rolling operators except Ref; use only arithmetic constants 0.000001, 0.0, 1.0, or 2.0.
Every expression must be valid for the AlphaPROBE prefix expression parser. Prefer one or two meaningful modifications, field diversity, and low redundancy with the parent.
Do not introduce size or valuation leaves that are absent from the allowed-leaves list; the search applies a market-cap exposure filter.
Never use infix symbols such as `*`, `/`, `+`, or `-`; always spell arithmetic as `Mul`, `Div`, `Add`, or `Sub`.
JSON schema: {{"expressions": ["..."], "explanations": ["..."]}}"""
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",
            "think": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.num_predict,
            },
        }
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                body = json.loads(response.read().decode("utf-8"))
            content = str(body.get("message", {}).get("content", ""))
            parsed = self._extract_json(content)
            if parsed is None:
                return self._fallback(node.payload.source)[:number], "fallback_invalid_json"
            expressions = parsed.get("expressions_fixed") or parsed.get("expressions") or []
            explanations = parsed.get("explanations") or []
            result: list[dict[str, str]] = []
            for index, expression in enumerate(expressions):
                if not isinstance(expression, str):
                    continue
                explanation = explanations[index] if index < len(explanations) else "LLM-generated DAG child"
                result.append({"expression": expression.strip(), "explanation": str(explanation)})
            if result:
                return result[:number], "ollama"
        except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            print(f"[generator fallback] {type(exc).__name__}: {exc}")
        return self._fallback(node.payload.source)[:number], "fallback_error"


SEEDS: tuple[tuple[str, str, str], ...] = (
    (
        "Div($high,$close)",
        "interday price movements",
        "daily high relative to close, a simple intraday strength or reversal signal",
    ),
    (
        "Div(Sub($close,$open),Add(Sub($high,$low),0.000001))",
        "interday price movements",
        "daily close-open movement normalized by the high-low range",
    ),
    (
        "TsRank($close,20)",
        "interday price movements",
        "time-series position of close within a 20-day window",
    ),
    (
        "Div(TsMean($volume,20),Add($volume,0.000001))",
        "volume movements",
        "recent average volume relative to current volume",
    ),
    (
        "Div(Div($amount,$volume),$high)",
        "intraday price-volume",
        "volume-weighted average price relative to the daily high",
    ),
    (
        "Div($amount,$volume)",
        "intraday price-volume",
        "volume-weighted average price reconstructed from amount and volume",
    ),
    (
        "Sub(Rank($oper_roe_lyr),Rank($gr_total_asset_lyr))",
        "fundamental quality-growth",
        "operating return on equity relative to latest total-asset growth",
    ),
    (
        "Rank($gr_total_asset_lyr)",
        "fundamental growth",
        "latest announced total-asset growth rate",
    ),
    (
        "Rank($book_to_market_ratio_lf)",
        "fundamental value",
        "cross-sectional rank of the latest announced book-to-market proxy",
    ),
    (
        "Rank($ratio_ep_ttm)",
        "fundamental value",
        "cross-sectional rank of the latest announced earnings-to-price proxy",
    ),
    (
        "Rank($oper_roe_lyr)",
        "fundamental quality",
        "cross-sectional rank of latest announced operating ROE proxy",
    ),
)


def prepare_output(path: Path, overwrite: bool) -> Path:
    path = path.expanduser().resolve()
    if path.exists() and any(path.iterdir()) and not overwrite:
        raise FileExistsError(f"Output directory is not empty: {path}; choose another --output or --overwrite")
    path.mkdir(parents=True, exist_ok=True)
    return path


def trace_text(graph: LocalKnowledgeGraph, node: ExpressionNode) -> str:
    return " -> ".join(
        f"{item.payload.source} ({item.description or item.topic or ''})"
        for item in graph.path_to_root(node)
    )


def choose_candidate(
    parser: LocalExpressionParser,
    pool: MainlineAlphaPool,
    raw_expression: str,
    max_length: int,
) -> tuple[str, Expression, dict[str, Any]] | None:
    raw_expression = raw_expression.strip().replace("`", "")
    if not raw_expression:
        return None
    windows = [5, 10, 20, 30, 60] if "%d" in raw_expression else [None]
    best: tuple[str, Expression, dict[str, Any]] | None = None
    for window in windows:
        expression_text = raw_expression.replace("%d", str(window)) if window is not None else raw_expression
        try:
            expression = parser.parse(expression_text)
            if not expression.is_featured:
                continue
            if len(parser.tokenize(expression_text)) > max_length:
                continue
            scored = pool.score_expression(expression)
        except (InvalidExpressionException, ValueError, IndexError, OutOfDataRangeError, RuntimeError, ZeroDivisionError) as exc:
            print(f"[candidate reject] {expression_text}: {type(exc).__name__}: {exc}")
            continue
        if scored.get("ic") is None or float(scored["ic"]) <= 0.0:
            continue
        if best is None or float(scored["objective"]) > float(best[2]["objective"]):
            best = (expression_text, expression, scored)
    return best


def candidate_passes_parent(
    scored: dict[str, Any],
    parent_scored: dict[str, Any],
    args: argparse.Namespace,
) -> bool:
    ic = float(scored.get("ic") or 0.0)
    icir = float(scored.get("icir") or 0.0)
    parent_icir = float(parent_scored.get("icir") or 0.0)
    parent_mutual = float(parent_scored.get("max_mutual_ic") or 0.0)
    max_mutual = float(scored.get("max_mutual_ic") or 0.0)
    if ic < args.ic_threshold:
        return False
    improves_icir = icir >= max(args.icir_floor, parent_icir * args.icir_decay_threshold)
    reduces_redundancy = max_mutual <= max(args.ic_new_threshold, parent_mutual * 0.90)
    return improves_icir or reduces_redundancy


def panel_metrics(
    expression: Expression,
    panel: TushareStockData,
    target: Expression,
    net_context: AlignedNetExcessContext,
) -> dict[str, Any]:
    raw = clean_tensor(expression.evaluate(panel))
    normalized = AlphaPool._normalize_by_day(raw)
    target_value = clean_tensor(target.evaluate(panel))
    ic_daily = batch_pearsonr(normalized, target_value)
    rank_daily = batch_spearman_linear(normalized, target_value)
    ic_daily = ic_daily[torch.isfinite(ic_daily)]
    rank_daily = rank_daily[torch.isfinite(rank_daily)]
    market_cap = clean_tensor(panel.get_named_feature("market_cap"))
    size_daily = batch_spearman_linear(raw, market_cap)
    size_daily = size_daily[torch.isfinite(size_daily)]
    net = net_context.score(raw)
    ic = float(ic_daily.mean().item()) if ic_daily.numel() else None
    icir = None
    if ic_daily.numel():
        icir = float(ic / (float(ic_daily.std(unbiased=False).item()) + 1e-6))
    return {
        "ic": ic,
        "icir": icir,
        "rank_ic": float(rank_daily.mean().item()) if rank_daily.numel() else None,
        "size_corr": float(size_daily.abs().mean().item()) if size_daily.numel() else None,
        "periods": int(ic_daily.numel()),
        "gross_excess": net.get("gross_excess"),
        "turnover": net.get("turnover"),
        "annual_cost": net.get("annual_cost"),
        "net_excess": net.get("net_excess"),
        "absolute_max_drawdown": net.get("absolute_max_drawdown"),
        "excess_max_drawdown": net.get("excess_max_drawdown"),
    }


def write_report(output: Path, rows: list[dict[str, Any]], metadata: dict[str, Any]) -> None:
    def fmt(value: Any) -> str:
        if value is None or (isinstance(value, float) and not np.isfinite(value)):
            return "n/a"
        try:
            return f"{float(value):.4f}"
        except (TypeError, ValueError):
            return str(value)

    flat_rows: list[dict[str, Any]] = []
    for row in rows:
        flat: dict[str, Any] = {
            "expression": row["expression"],
            "topic": row.get("topic"),
            "depth": row.get("depth"),
            "retriever_objective": row.get("retriever_objective"),
        }
        for split in ("train", "valid", "test"):
            for key, value in row[split].items():
                if isinstance(value, (dict, list, torch.Tensor)):
                    continue
                flat[f"{split}_{key}"] = value
        flat_rows.append(flat)
    frame = pd.DataFrame(flat_rows)
    if not frame.empty and "test_net_excess" in frame:
        frame = frame.sort_values(["test_net_excess", "test_rank_ic"], ascending=False, na_position="last")
    frame.to_csv(output / "candidates.csv", index=False)
    lines = [
        "# AlphaPROBE Mainline Tushare Run",
        "",
        f"- method: `{metadata['method_id']}`",
        f"- alignment rule: `{metadata['alignment_rule_version']}`",
        f"- universe: {metadata['universe']} ({metadata['universe_size']} instruments)",
        f"- generator: `{metadata['generator']['provider']}` / `{metadata['generator']['model']}`",
        "- semantic embedding: disabled because the local embedding model is unavailable",
        "- train-only objective includes signed positive IC and aligned local net excess; valid/test are evaluation only",
        "",
        "## Results",
        "",
    ]
    if frame.empty:
        lines.append("No candidate survived the local parser and positive-IC admission rules.")
    else:
        for _, item in frame.iterrows():
            lines.extend(
                [
                    f"### `{item['expression']}`",
                    "",
                    f"topic: {item.get('topic', '')}; depth: {item.get('depth', '')}",
                    "",
                    f"train: IC={fmt(item.get('train_ic'))}, RankIC={fmt(item.get('train_rank_ic'))}, net={fmt(item.get('train_net_excess'))}",
                    f"valid: IC={fmt(item.get('valid_ic'))}, RankIC={fmt(item.get('valid_rank_ic'))}, net={fmt(item.get('valid_net_excess'))}",
                    f"test: IC={fmt(item.get('test_ic'))}, RankIC={fmt(item.get('test_rank_ic'))}, net={fmt(item.get('test_net_excess'))}",
                    "",
                ]
            )
    (output / "candidates.report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> Path:
    validate_alignment_config(alignment_config_snapshot())
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = torch.device("cuda:0" if args.device == "auto" and torch.cuda.is_available() else args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError(f"Requested {device}, but CUDA is unavailable")
    args.cache_root = args.cache_root.expanduser().resolve()
    args.price_root = args.price_root.expanduser().resolve()
    args.cap_root = args.cap_root.expanduser().resolve()
    args.financial_root = args.financial_root.expanduser().resolve()
    output = prepare_output(args.output, args.overwrite)
    if args.overwrite:
        (output / "training_history.json").write_text("[]\n", encoding="utf-8")

    panels, target, metadata = load_panels(args, device)
    (output / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )
    named_fields = metadata["feature_search"]["search_fields"]
    parser = LocalExpressionParser(named_fields)
    graph = LocalKnowledgeGraph(parser, args.depth_limit, args.max_length)
    train_context = AlignedNetExcessContext(
        frame=panels["train"].df_bak,
        calendar=panels["train"]._calendar,
        data=panels["train"],
        start_date=panels["train"]._start_time,
        end_date=panels["train"]._end_time,
        cycle=args.cycle,
        label_offset=ALIGNMENT_LABEL_OFFSET,
        groups=ALIGNMENT_GROUPS,
        round_trip_cost=ALIGNMENT_ROUND_TRIP_COST,
    )
    pool = MainlineAlphaPool(
        args.pool_capacity,
        panels["train"],
        target,
        graph=graph,
        net_context=train_context,
        ic_mut_threshold=args.ic_mut_threshold,
        top_k=args.top_k,
        depth_decay=args.depth_decay,
        times_decay=args.times_decay,
        net_excess_weight=args.net_excess_weight,
        net_excess_scale=args.net_excess_scale,
        max_size_corr=args.max_size_corr,
    )

    lineage: list[dict[str, Any]] = []
    seed_results: list[dict[str, Any]] = []
    for expression_text, topic, description in SEEDS:
        try:
            expression = parser.parse(expression_text)
            scored = pool.score_expression(expression)
            node = graph.build_expression_node(
                expression_text,
                topic,
                description,
                args.max_length,
                float(scored["ic"]),
                float(scored["icir"] or 0.0),
            )
            if node is None:
                seed_results.append({"expression": expression_text, "status": "invalid_or_too_long"})
                continue
            if pool.try_new_expr(expression, topic, description, node, scored):
                graph.insert(node, None)
                pool.register_expression_node(node)
                seed_results.append({"expression": expression_text, "status": "accepted", "ic": scored["ic"], "net_excess": scored["net"].get("net_excess")})
            else:
                seed_results.append({"expression": expression_text, "status": "rejected", "ic": scored.get("ic"), "net_excess": scored["net"].get("net_excess")})
        except (InvalidExpressionException, ValueError, IndexError, OutOfDataRangeError, RuntimeError) as exc:
            seed_results.append({"expression": expression_text, "status": "error", "error": f"{type(exc).__name__}: {exc}"})
    (output / "seed_results.json").write_text(json.dumps(seed_results, ensure_ascii=False, indent=2, default=json_default) + "\n", encoding="utf-8")

    generator = OllamaGenerator(args, named_fields)
    generation_statuses: list[str] = []
    seen = {str(pool.exprs[index]) for index in range(pool.size)}
    for iteration in range(1, args.iterations + 1):
        nodes, parents = pool.search()
        iteration_record: dict[str, Any] = {"iteration": iteration, "parents": [], "accepted": []}
        for node, parent in zip(nodes, parents):
            if parent is None:
                continue
            trace = trace_text(graph, node)
            generated, status = generator.generate(node, trace, args.generate_num)
            generation_statuses.append(status)
            parent_scored = pool.score_expression(parent)
            parent_item = {"expression": node.payload.source, "retriever_score": float(pool.objective_scores[list(pool.exprs[:pool.size]).index(parent)]) if parent in pool.exprs[:pool.size] else None, "generation_status": status, "candidates": []}
            for generated_item in generated:
                raw_expression = generated_item.get("expression", "")
                selected = choose_candidate(parser, pool, raw_expression, args.max_length)
                if selected is None:
                    parent_item["candidates"].append({"expression": raw_expression, "status": "invalid_or_nonpositive"})
                    continue
                expression_text, expression, scored = selected
                if expression_text in seen or not candidate_passes_parent(scored, parent_scored, args):
                    parent_item["candidates"].append({"expression": expression_text, "status": "rejected_parent_rule", "ic": scored.get("ic"), "icir": scored.get("icir"), "net_excess": scored["net"].get("net_excess")})
                    continue
                description = str(generated_item.get("explanation") or "LLM-generated DAG child")
                child = graph.build_expression_node(expression_text, node.topic or "generated", description, args.max_length, float(scored["ic"]), float(scored["icir"] or 0.0))
                if child is None:
                    parent_item["candidates"].append({"expression": expression_text, "status": "graph_rejected"})
                    continue
                if pool.try_new_expr(expression, node.topic or "generated", description, child, scored):
                    if graph.insert(child, node):
                        pool.register_expression_node(child)
                        seen.add(expression_text)
                        parent_item["candidates"].append({"expression": expression_text, "status": "accepted", "ic": scored.get("ic"), "icir": scored.get("icir"), "net_excess": scored["net"].get("net_excess")})
                        iteration_record["accepted"].append(expression_text)
                        lineage.append({"parent": node.payload.source, "child": expression_text, "topic": node.topic, "description": description, "trace": trace, "iteration": iteration})
                    else:
                        parent_item["candidates"].append({"expression": expression_text, "status": "graph_duplicate"})
                else:
                    parent_item["candidates"].append({"expression": expression_text, "status": "pool_rejected"})
            iteration_record["parents"].append(parent_item)
        history_path = output / "training_history.json"
        existing = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else []
        existing.append(iteration_record)
        history_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2, default=json_default) + "\n", encoding="utf-8")
        print(json.dumps({"iteration": iteration, "pool_size": pool.size, "accepted": iteration_record["accepted"], "generation_statuses": generation_statuses[-len(nodes):]}, ensure_ascii=False))

    metadata["generation_statuses"] = generation_statuses
    metadata["seed_count"] = len(seed_results)
    metadata["accepted_count"] = pool.size
    (output / "run_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2, default=json_default) + "\n", encoding="utf-8")
    (output / "lineage.json").write_text(json.dumps(lineage, ensure_ascii=False, indent=2, default=json_default) + "\n", encoding="utf-8")
    (output / "final_pool.json").write_text(json.dumps(pool.to_dict(), ensure_ascii=False, indent=2, default=json_default) + "\n", encoding="utf-8")

    split_contexts = {
        name: AlignedNetExcessContext(
            frame=panel.df_bak,
            calendar=panel._calendar,
            data=panel,
            start_date=panel._start_time,
            end_date=panel._end_time,
            cycle=args.cycle,
            label_offset=ALIGNMENT_LABEL_OFFSET,
            groups=ALIGNMENT_GROUPS,
            round_trip_cost=ALIGNMENT_ROUND_TRIP_COST,
        )
        for name, panel in panels.items()
    }
    rows: list[dict[str, Any]] = []
    for index in range(pool.size):
        expression = pool.exprs[index]
        if expression is None:
            continue
        row = {
            "expression": str(expression),
            "topic": pool.topics[index],
            "description": pool.descriptions[index],
            "depth": pool.expr2node[index].depth if pool.expr2node[index] is not None else None,
            "retriever_objective": float(pool.objective_scores[index]),
        }
        for name, panel in panels.items():
            row[name] = panel_metrics(expression, panel, target, split_contexts[name])
        rows.append(row)
    (output / "candidates.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2, default=json_default) + "\n", encoding="utf-8")
    write_report(output, rows, metadata)
    print(f"AlphaPROBE mainline run completed: {output}")
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--price-root", type=Path, default=DEFAULT_PRICE_ROOT)
    parser.add_argument("--cap-root", type=Path, default=DEFAULT_CAP_ROOT)
    parser.add_argument("--financial-root", type=Path, default=DEFAULT_FINANCIAL_ROOT)
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
    parser.add_argument("--backtrack-days", type=int, default=512)
    parser.add_argument("--universe-limit", type=int, default=None, help="explicit smoke subset; omit for full A")
    parser.add_argument("--feature-set", choices=["price_volume", "verified", "fundamental_core", "all_active"], default="verified")
    parser.add_argument("--extra-fields", default=None)
    parser.add_argument("--max-extra-fields", type=int, default=64)
    parser.add_argument("--allow-unverified-fields", action="store_true")
    parser.add_argument("--allow-blocked-fields", action="store_true")
    parser.add_argument("--pool-capacity", type=int, default=12)
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--generate-num", type=int, default=3)
    parser.add_argument("--depth-limit", type=int, default=7)
    parser.add_argument("--max-length", type=int, default=50)
    parser.add_argument("--depth-decay", type=float, default=0.05)
    parser.add_argument("--times-decay", type=float, default=0.10)
    parser.add_argument("--ic-mut-threshold", type=float, default=0.90)
    parser.add_argument("--ic-threshold", type=float, default=0.002)
    parser.add_argument("--icir-floor", type=float, default=0.05)
    parser.add_argument("--icir-decay-threshold", type=float, default=0.70)
    parser.add_argument("--ic-new-threshold", type=float, default=0.45)
    parser.add_argument("--net-excess-weight", type=float, default=0.10)
    parser.add_argument("--net-excess-scale", type=float, default=0.10)
    parser.add_argument(
        "--max-size-corr",
        type=float,
        default=0.35,
        help="maximum mean absolute daily Spearman exposure to market_cap; use 1.0 to disable the practical filter",
    )
    parser.add_argument("--generator", choices=["ollama", "fallback"], default="ollama")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--model", default="goekdenizguelmez/JOSIEFIED-Qwen3:latest")
    parser.add_argument("--temperature", type=float, default=0.30)
    parser.add_argument("--num-predict", type=int, default=800)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--seed", type=int, default=20260918)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.cycle < 1 or args.iterations < 1 or args.generate_num < 1:
        raise ValueError("cycle, iterations and generate-num must be positive")
    if args.max_extra_fields < 0:
        raise ValueError("max-extra-fields must be non-negative")
    if args.max_size_corr is not None and not 0.0 <= args.max_size_corr <= 1.0:
        raise ValueError("max-size-corr must be between 0 and 1")
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
