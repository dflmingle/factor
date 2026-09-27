"""宽字段 GP 新候选 × 2026-09-19 旧分簇成员：相关重叠检查（本地，零平台算力）。

问题：2026-09-24 宽字段 GP 新挖出的 253 条候选（尤其 40-60% 换手档），
是否落在 2026-09-19 那 13 个旧簇之内？

方法：用 GP 引擎（与筛选同一条口径）把两侧公式都物化为 signal-date 面板，
按日横截面 Spearman（与分簇同一统计量、同一 0.80 阈值）求相关矩阵。
快速通道用整日矩阵一次算全；|rho| >= 0.60 的配对再用逐日 pairwise-complete 重算。
"""
from __future__ import annotations

import argparse
import gc
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import alphaprobe_gp_tushare as gp  # noqa: E402
import relaxed_gp_screen_20260924 as screen  # noqa: E402
from alphagen.data.expression import Constant, Expression, Operator  # noqa: E402
from local_safe_financial_candidates import CrossSectionalZScore  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CAND_PATH = ROOT / "research_reports/platform_alignment/relaxed-gp-20260924/screen2/screened_candidates.csv"
PAIRS_PATH = ROOT / "research_reports/platform_alignment/positive-factor-pair-correlation-20260917.pairs.csv"
CLUSTER_PATH = ROOT / "research_reports/platform_alignment/all-factor-cluster-expansion-20260919.clusters.csv"
UNCLUSTERED = "未入簇"
DEFAULT_OUT = ROOT / "research_reports/platform_alignment/cluster-overlap-20260924"
THRESHOLD = 0.80
EXACT_FLOOR = 0.60
MIN_PER_DATE = 100


class CrossZScore(CrossSectionalZScore):
    """平台 ZSCORE：按日横截面标准化，复用仓库既有 CrossSectionalZScore 口径。"""


class IfElse(Operator):
    """平台 IF(cond, a, b)：cond > 0 取 a，否则取 b。"""

    def __init__(self, cond, lhs, rhs) -> None:
        self._cond = cond if isinstance(cond, Expression) else Constant(cond)
        self._lhs = lhs if isinstance(lhs, Expression) else Constant(lhs)
        self._rhs = rhs if isinstance(rhs, Expression) else Constant(rhs)

    @classmethod
    def n_args(cls) -> int:
        return 3

    @classmethod
    def category_type(cls):
        return Operator

    def evaluate(self, data, period: slice = slice(0, 1)) -> torch.Tensor:
        cond = self._cond.evaluate(data, period)
        left = self._lhs.evaluate(data, period)
        right = self._rhs.evaluate(data, period)
        mask = torch.isfinite(cond) & (cond > 0)
        return torch.where(mask, left, right)

    def __str__(self) -> str:
        return f"IfElse({self._cond},{self._lhs},{self._rhs})"

    @property
    def is_featured(self) -> bool:
        return self._cond.is_featured or self._lhs.is_featured or self._rhs.is_featured


def parse_cluster_map(path: Path) -> dict[str, str]:
    """Member -> cluster label from the 2026-09-19 all-factor expansion.

    That artifact is the canonical naming: B01-B12 positive base clusters plus
    N01-N33 negative-net clusters, formed on the same |rho| >= 0.80 signal-date
    rank-correlation basis.  Visible composites are annotated there but never
    create clusters, so a member absent from the file is not cluster-defining
    even when it is a known composite formula.
    """
    frame = pd.read_csv(path)
    label_column = "cluster" if "cluster" in frame.columns else frame.columns[0]
    mapping: dict[str, str] = {}
    for label, names in zip(frame[label_column], frame["member_names"]):
        if not isinstance(names, str):
            continue
        for name in names.split(";"):
            name = name.strip()
            if name:
                mapping.setdefault(name, str(label).strip())
    return mapping


def load_candidates(path: Path, limit: int | None) -> pd.DataFrame:
    keep = ["band", "formula", "net", "turnover", "net_y2026", "s_i_rank", "corr_size",
            "corr_max_seat", "corr_max_seat_name", "delta_points"]
    frame = pd.read_csv(path)[keep].drop_duplicates(subset=["formula"]).reset_index(drop=True)
    if limit:
        frame = frame.head(limit).copy()
    return frame


def load_members(path: Path, limit: int | None) -> pd.DataFrame:
    columns = {"factor_a_name", "factor_a_formula", "factor_b_name", "factor_b_formula"}
    frame = pd.read_csv(path, usecols=lambda c: c in columns)
    records: dict[str, str] = {}
    for _, row in frame.iterrows():
        for side in ("a", "b"):
            name = row.get(f"factor_{side}_name")
            formula = row.get(f"factor_{side}_formula")
            if isinstance(name, str) and isinstance(formula, str) and formula.strip():
                records.setdefault(name, formula.strip())
    out = pd.DataFrame(sorted(records.items()), columns=["name", "formula"])
    if limit:
        out = out.head(limit).copy()
    return out


def rank_array(panel: pd.DataFrame) -> np.ndarray:
    values = panel.to_numpy(dtype="float64")
    out = np.full(values.shape, np.nan, dtype="float32")
    for index in range(values.shape[0]):
        row = values[index]
        ok = np.isfinite(row)
        if ok.sum() < MIN_PER_DATE:
            continue
        out[index, ok] = pd.Series(row[ok]).rank().to_numpy(dtype="float32")
    return out


def accumulate(corr_sum: np.ndarray, corr_cnt: np.ndarray, ranks: np.ndarray) -> None:
    finite = np.isfinite(ranks)
    counts = finite.sum(axis=1)
    valid = counts >= MIN_PER_DATE
    if not valid.any():
        return
    zeros = np.where(finite, ranks, 0.0)
    means = zeros.sum(axis=1, keepdims=True) / np.maximum(counts[:, None], 1)
    centered = np.where(finite, ranks - means, 0.0)
    norms = np.sqrt((centered ** 2).sum(axis=1))
    denom = np.outer(norms, norms)
    with np.errstate(invalid="ignore", divide="ignore"):
        gram = (centered @ centered.T) / denom
    ok = np.outer(valid, valid) & np.isfinite(gram)
    corr_sum += np.where(ok, gram, 0.0)
    corr_cnt += ok


def exact_pair_corr(left: np.ndarray, right: np.ndarray) -> float:
    values = []
    for index in range(left.shape[0]):
        x, y = left[index], right[index]
        ok = np.isfinite(x) & np.isfinite(y)
        if ok.sum() < MIN_PER_DATE:
            continue
        a = pd.Series(x[ok]).rank().to_numpy()
        b = pd.Series(y[ok]).rank().to_numpy()
        if a.std() == 0 or b.std() == 0:
            continue
        values.append(float(np.corrcoef(a, b)[0, 1]))
    return float(np.mean(values)) if values else float("nan")


ROLLING_NAMES = frozenset({
    "Ref", "TsMean", "TsSum", "TsStd", "TsIr", "TsMinMaxDiff", "TsMaxDiff", "TsMinDiff",
    "TsVar", "TsSkew", "TsKurt", "TsMax", "TsMin", "TsMed", "TsMad", "TsRank", "TsDelta",
    "TsDiv", "TsPctChange", "TsWMA", "TsEMA", "TsCov", "TsCorr",
    "DELAY", "MA", "SUM", "STDDEV", "TS_IR", "TS_MAX_MIN_DIFF", "TS_MAX_DIFF", "TS_MIN_DIFF",
    "VAR", "TS_SKEW", "TS_KURT", "TS_MAX", "TS_MIN", "TS_MEDIAN", "TS_MAD", "TS_RANK", "DIFF",
    "RETURNS", "TS_DIV", "WMA", "EMA", "COV", "CORR", "COVARIANCE", "CORRELATION",
})


def iter_calls(formula: str):
    """Yield (operator, top-level argument text) for every call in the formula."""
    for match in re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(", formula):
        name = match.group(1)
        index = match.end()
        depth = 1
        start = index
        while index < len(formula) and depth:
            char = formula[index]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            index += 1
        yield name, formula[start:index - 1]


def split_top_level(arguments: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    current = ""
    for char in arguments:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += char
    parts.append(current)
    return [piece.strip() for piece in parts]


def max_rolling_window(formula: str) -> int:
    """Largest rolling window in the formula; 0 when no rolling operator is present.

    AlphaPROBE unfolds each rolling operator into an (n_days, stocks, window)
    tensor, so the peak allocation is n_days * stocks * window bytes.  The
    full-history evaluator sets n_days to the whole 2018-2026 panel, which
    makes long windows impossible to materialise locally.
    """
    largest = 0
    for name, arguments in iter_calls(formula):
        if name not in ROLLING_NAMES:
            continue
        pieces = split_top_level(arguments)
        if len(pieces) >= 2 and re.fullmatch(r"\d+", pieces[-1]):
            largest = max(largest, int(pieces[-1]))
    return largest


class CompareExpression(Expression):
    """平台公式里的 `a > b` 等比较：返回 1/0 布尔式，供 IF 使用。

    AlphaPROBE 自带的 Greater/Less 是逐元素取大/取小，与平台公式把比较结果
    当成条件（`IF(cond, a, b)`，cond 为正取 a）的语义不同，所以这里单独实现。
    """

    def __init__(self, lhs, rhs, op: str) -> None:
        self._lhs = lhs if isinstance(lhs, Expression) else Constant(lhs)
        self._rhs = rhs if isinstance(rhs, Expression) else Constant(rhs)
        self._op = op

    def evaluate(self, data, period: slice = slice(0, 1)) -> torch.Tensor:
        lhs = self._lhs.evaluate(data, period)
        rhs = self._rhs.evaluate(data, period)
        finite = torch.isfinite(lhs) & torch.isfinite(rhs)
        if self._op == "gt":
            mask = lhs > rhs
        elif self._op == "lt":
            mask = lhs < rhs
        elif self._op == "ge":
            mask = lhs >= rhs
        else:
            mask = lhs <= rhs
        result = (mask & finite).to(lhs.dtype)
        return torch.where(finite, result, torch.full_like(result, float("nan")))

    def __str__(self) -> str:
        return f"Compare({self._lhs},{self._op},{self._rhs})"

    @property
    def is_featured(self) -> bool:
        return self._lhs.is_featured or self._rhs.is_featured


class LeafExpression(Expression):
    """PandaAI 字段叶子：转发到本地字段存储，并继承表达式的比较协议。"""

    def __init__(self, field) -> None:
        self._field = field

    def evaluate(self, data, period: slice = slice(0, 1)) -> torch.Tensor:
        return self._field.evaluate(data, period)

    def __str__(self) -> str:
        return str(self._field)

    @property
    def is_featured(self) -> bool:
        return True


def patch_expression_comparisons() -> None:
    """把 `>`/`<`/`>=`/`<=` 换成平台公式的比较语义。"""
    Expression.__gt__ = lambda self, other: CompareExpression(self, other, "gt")
    Expression.__lt__ = lambda self, other: CompareExpression(self, other, "lt")
    Expression.__ge__ = lambda self, other: CompareExpression(self, other, "ge")
    Expression.__le__ = lambda self, other: CompareExpression(self, other, "le")


def wrap_field_leaves(namespace: dict[str, object]) -> None:
    """字段叶子换成可参与比较的表达式节点；算子与别名保持原样。"""
    from pandaai_fields_local import PandaAIField

    for key, value in list(namespace.items()):
        if isinstance(value, PandaAIField):
            namespace[key] = LeafExpression(value)


def share_store_caches(stores) -> None:
    """Let several field stores share one indexed frame and one financial cache.

    Both caches cost more than a gigabyte on the full-A panel, so a chunked
    evaluation keeps a single copy: the first store that needs one builds it and
    every other store reuses that object.
    """
    import types

    index_holder: dict[str, object] = {}
    financial_holder: dict[str, object] = {}
    original_index = type(stores[0])._index_frame
    original_financial = type(stores[0])._ensure_financial_cache

    def shared_index_frame(self, _holder=index_holder, _original=original_index):
        if _holder.get("value") is None:
            _holder["value"] = _original(self)
        return _holder["value"]

    def shared_financial_cache(self, _holder=financial_holder, _original=original_financial):
        if _holder.get("value") is None:
            _holder["value"] = _original(self)
        return _holder["value"]

    for store in stores:
        store._index_frame = types.MethodType(shared_index_frame, store)
        store._ensure_financial_cache = types.MethodType(shared_financial_cache, store)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--limit-candidates", type=int, default=0)
    parser.add_argument("--limit-members", type=int, default=0)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--stage", choices=["eval", "correlate", "all"], default="all")
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--chunk", type=int, default=32,
                        help="candidate panels held in memory per correlation chunk")
    parser.add_argument("--max-window", type=int, default=0,
                        help="skip formulas whose largest rolling window exceeds this; 0 disables")
    parser.add_argument("--eval-mode", choices=["chunked", "chunkmajor", "full"],
                        default="chunked",
                        help="chunked evaluates short signal-date windows; full reproduces the "
                             "original whole-panel evaluation")
    parser.add_argument("--day-chunk", type=int, default=30,
                        help="signal dates per evaluation chunk in chunked mode")
    parser.add_argument("--members-only", action="store_true",
                        help="evaluate only the historical cluster members")
    parser.add_argument("--skip-heavy-members", action="store_true",
                        help="skip member formulas above --max-window instead of attempting them")
    parser.add_argument("--member-indices", default="",
                        help="comma-separated member indices to evaluate (blank = all)")
    parser.add_argument("--extra-members", default="",
                        help="CSV with name,formula,cluster appended as extra cluster members")
    parser.add_argument("--threads", type=int, default=0,
                        help="torch CPU threads; 0 keeps the torch default")
    args = parser.parse_args()

    if args.threads > 0:
        torch.set_num_threads(args.threads)

    started = time.time()
    out_dir = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    candidates = load_candidates(CAND_PATH, args.limit_candidates or None)
    band_order = {"40_60": 0, "30_40": 1, "le30": 2, "gt60": 3}
    candidates = candidates.assign(_band_rank=candidates["band"].map(band_order).fillna(9)).sort_values(["_band_rank", "net_y2026"], ascending=[True, False]).drop(columns=["_band_rank"]).reset_index(drop=True)
    members = load_members(PAIRS_PATH, args.limit_members or None)
    cluster_map = parse_cluster_map(CLUSTER_PATH)
    if args.extra_members:
        extra_frame = pd.read_csv(args.extra_members)
        start_at = (int(members.index.max()) + 1) if len(members) else 0
        extra_frame = extra_frame[["name", "formula", "cluster"]].reset_index(drop=True)
        extra_frame.index = range(start_at, start_at + len(extra_frame))
        members = pd.concat([members, extra_frame[["name", "formula"]]])
        for _, extra_row in extra_frame.iterrows():
            cluster_map[str(extra_row["name"])] = str(extra_row["cluster"])
        print(f"extra_members={len(extra_frame)} indices={start_at}..{start_at + len(extra_frame) - 1}",
              flush=True)
    print(f"candidates={len(candidates)} members={len(members)} "
          f"members_in_clusters={sum(1 for n in members['name'] if n in cluster_map)}", flush=True)

    cache_root = gp.DEFAULT_CACHE_ROOT
    cap_root = cache_root / "tushare_factor_recheck" / "daily_basic_full_a"
    calendar = gp.load_trade_dates(cache_root)
    data_start = pd.Timestamp(gp.ALIGNMENT_DATA_START)
    start, end = pd.Timestamp(gp.ALIGNMENT_START), pd.Timestamp(gp.ALIGNMENT_END)
    frame = gp.load_full_a_data(gp.DEFAULT_BATCH_ROOT, cap_root, data_start, end).sort_values(
        ["instrument", "date"], ignore_index=True)
    # 下游面板一律 float32（字段存储 _materialize 会转 float32），
    # 但 pandas 默认按 float64 读入并在建索引时再复制一份 float64 中间量。
    # 先在原位降精度，可把整帧与索引帧的内存砍半，数值口径不变。
    downcast = {
        column: "float32"
        for column in frame.columns
        if frame[column].dtype == "float64"
    }
    if downcast:
        frame = frame.astype(downcast)
        gc.collect()
    print(f"frame rows={len(frame)} columns={len(frame.columns)} downcast={len(downcast)} "
          f"elapsed={time.time() - started:.1f}s", flush=True)
    stock_ids = sorted(frame["instrument"].astype(str).unique())
    cal = [d for d in calendar if data_start <= d <= end]
    device = torch.device(args.device)
    data = gp.TushareStockData.from_aligned_frame(
        frame=frame, calendar=cal, instrument=stock_ids, start_time=gp.date_text(start),
        end_time=gp.date_text(end), max_backtrack_days=756, max_future_days=0,
        device=device, financial_root=gp.DEFAULT_FINANCIAL_ROOT)
    context = gp.AlignedNetExcessContext(
        frame=frame, calendar=cal, data=data, start_date=start, end_date=end,
        cycle=screen.CYCLE, label_offset=1, groups=10, round_trip_cost=screen.COST)
    signal_dates = [pd.Timestamp(d) for d in context.signal_dates]
    namespace = gp.expression_namespace()
    namespace.update({"DELAY": namespace["Ref"], "ZSCORE": CrossZScore, "IF": IfElse,
                      "ZScore": CrossZScore})
    patch_expression_comparisons()
    wrap_field_leaves(namespace)

    print(f"data ready in {time.time() - started:.1f}s signal_dates={len(signal_dates)} "
          f"stocks={len(stock_ids)}", flush=True)

    calendar_positions = {date: index for index, date in enumerate(cal)}
    chunk_spans: list[tuple[int, int, object, list[int]]] = []
    if args.eval_mode == "chunked":
        span = max(int(args.day_chunk), 1)
        chunk_stores = []
        for start_at in range(0, len(signal_dates), span):
            stop_at = min(start_at + span, len(signal_dates))
            first_date, last_date = signal_dates[start_at], signal_dates[stop_at - 1]
            warm_position = max(calendar_positions[first_date] - 800, 0)
            warm_start = cal[warm_position]
            chunk_frame = frame[(frame["date"] >= warm_start) & (frame["date"] <= last_date)]
            chunk_obj = gp.TushareStockData.from_aligned_frame(
                frame=chunk_frame, calendar=cal, instrument=stock_ids,
                start_time=gp.date_text(first_date), end_time=gp.date_text(last_date),
                max_backtrack_days=756, max_future_days=0, device=device,
                financial_root=gp.DEFAULT_FINANCIAL_ROOT)
            del chunk_frame
            gc.collect()
            chunk_dates = [pd.Timestamp(value) for value in chunk_obj._evaluation_dates]
            index_of = {date: index for index, date in enumerate(chunk_dates)}
            positions = [index_of[date] for date in signal_dates[start_at:stop_at]]
            chunk_spans.append((start_at, stop_at, chunk_obj, positions))
            chunk_stores.append(chunk_obj.pandaai_field_store)
        # 分块对象先建好（此刻常驻内存最低），再建共享索引帧与财务缓存：
        # 两次峰值不再叠加，整段设置的峰值由“单次构造瞬时量”决定。
        base_store = data.pandaai_field_store
        shared_index = base_store._index_frame()
        shared_financial = base_store._ensure_financial_cache()
        shared_status = base_store._status_cache
        print(f"[chunk] shared caches rows={len(shared_index)} "
              f"elapsed={time.time() - started:.1f}s", flush=True)
        for store in chunk_stores:
            store._frame_indexed = shared_index
            store._financial_cache = shared_financial
            store._status_cache = shared_status

        for start_at, stop_at, chunk_obj, positions in chunk_spans:
            print(f"[chunk] {start_at}:{stop_at} {signal_dates[start_at].date()}.."
                  f"{signal_dates[stop_at - 1].date()} n_days={len(chunk_obj._evaluation_dates)}",
                  flush=True)
        print(f"[chunk] {len(chunk_spans)} chunks ready in {time.time() - started:.1f}s", flush=True)

    def rank_of(formula: str, tag: str) -> tuple[np.ndarray | None, str]:
        try:
            expression = gp.evaluate_formula(formula, namespace)
            if args.eval_mode == "full":
                with torch.no_grad():
                    values = gp.finite_as_nan(expression.evaluate(data))
                panel = screen.panel_frame(values, context.signal_data_positions, signal_dates, stock_ids)
                return rank_array(panel), ""
            rows = np.full((len(signal_dates), len(stock_ids)), np.nan, dtype="float32")
            for start_at, stop_at, chunk_obj, positions in chunk_spans:
                with torch.no_grad():
                    values = gp.finite_as_nan(expression.evaluate(chunk_obj))
                block = values.detach().cpu().numpy()
                rows[start_at:stop_at] = block[positions]
        except Exception as exc:  # noqa: BLE001
            return None, f"{type(exc).__name__}: {exc}"
        return rank_array(pd.DataFrame(rows, index=signal_dates, columns=stock_ids)), ""

    # ------------------------------------------------------------------
    # 阶段 1/2：逐条物化 signal-date 排名面板（落盘，可断点续跑）
    # ------------------------------------------------------------------
    panels_dir = out_dir / "panels"
    panels_dir.mkdir(parents=True, exist_ok=True)
    shard_count = max(int(args.shard_count), 1)
    shard_index = int(args.shard_index) % shard_count
    failures_path = panels_dir / f"failures_shard{shard_index}.tsv"

    def panel_path(kind: str, idx: int) -> Path:
        return panels_dir / f"{kind}_{idx:04d}.npy"

    skipped_path = panels_dir / f"skipped_shard{shard_index}.tsv"

    def evaluate_into(kind: str, idx: int, formula: str, extra: str) -> str:
        target = panel_path(kind, idx)
        if target.exists():
            return "reused"
        if args.max_window > 0:
            window = max_rolling_window(formula)
            if window > args.max_window:
                with skipped_path.open("a", encoding="utf-8") as handle:
                    handle.write(f"{kind}\t{idx}\t{extra}\t{window}\t{formula}\n")
                print(f"  [eval] {kind}_{idx:04d} SKIPPED window={window} > {args.max_window}", flush=True)
                return "skipped"
        began = time.time()
        ranks, error = rank_of(formula, tag=f"{kind}_{idx:04d}")
        elapsed = time.time() - began
        if ranks is None:
            with failures_path.open("a", encoding="utf-8") as handle:
                handle.write(f"{kind}\t{idx}\t{extra}\t{error}\t{formula}\n")
            print(f"  [eval] {kind}_{idx:04d} FAILED {elapsed:.0f}s :: {error}"[:200], flush=True)
            return "failed"
        np.save(target, ranks)
        covered = int(np.isfinite(ranks).any(axis=1).sum())
        print(f"  [eval] {kind}_{idx:04d} ok {elapsed:.0f}s days={covered}/{ranks.shape[0]}", flush=True)
        return "ok"
    if args.stage in {"eval", "all"}:
        todo_members = [i for i in members.index.tolist() if i % shard_count == shard_index]
        if args.member_indices.strip():
            wanted = {int(v) for v in args.member_indices.replace(" ", "").split(",") if v}
            todo_members = [i for i in todo_members if i in wanted]
        if args.eval_mode == "chunkmajor":
            def _rss_gb() -> float:
                try:
                    import ctypes
                    import ctypes.wintypes as wt

                    class Counters(ctypes.Structure):
                        _fields_ = [
                            ("cb", wt.DWORD),
                            ("PageFaultCount", wt.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t),
                            ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t),
                            ("PeakPagefileUsage", ctypes.c_size_t),
                        ]

                    counters = Counters()
                    counters.cb = ctypes.sizeof(counters)
                    kernel32 = ctypes.windll.kernel32
                    psapi = ctypes.windll.psapi
                    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
                    psapi.GetProcessMemoryInfo.restype = ctypes.c_int
                    psapi.GetProcessMemoryInfo.argtypes = [
                        ctypes.c_void_p, ctypes.POINTER(Counters), wt.DWORD]
                    handle = kernel32.GetCurrentProcess()
                    if psapi.GetProcessMemoryInfo(
                            ctypes.c_void_p(handle), ctypes.byref(counters), counters.cb):
                        return counters.WorkingSetSize / float(1024 ** 3)
                except Exception:  # noqa: BLE001
                    pass
                return float("nan")

            todo: list[tuple[str, int, str, str]] = []
            for idx in todo_members:
                row = members.loc[idx]
                todo.append(("member", idx, str(row["formula"]), str(row["name"])))
            if not args.members_only:
                for idx in [i for i in candidates.index.tolist() if i % shard_count == shard_index]:
                    row = candidates.loc[idx]
                    todo.append(("cand", idx, str(row["formula"]), str(row["band"])))
            pending = [item for item in todo if not panel_path(item[0], item[1]).exists()]
            print(f"[chunkmajor] pending={len(pending)}/{len(todo)} "
                  f"day_chunk={args.day_chunk} signal_dates={len(signal_dates)}", flush=True)
            if not pending:
                print("[chunkmajor] nothing to do", flush=True)
                return 0
            keys = [f"{kind}_{idx:04d}" for kind, idx, _, _ in pending]
            rows = {key: np.full((len(signal_dates), len(stock_ids)), np.nan, dtype="float32")
                    for key in keys}
            span = max(int(args.day_chunk), 1)
            chunk_starts = list(range(0, len(signal_dates), span))
            partial_path = panels_dir / "chunkmajor_partial.npz"
            done_chunks: set[int] = set()
            if partial_path.exists():
                try:
                    with np.load(partial_path) as saved:
                        if [str(value) for value in saved["__keys__"].tolist()] == keys:
                            for key in keys:
                                rows[key] = saved[key]
                            done_chunks = {int(value) for value in saved["__chunks__"].tolist()}
                            print(f"[chunkmajor] resumed {len(done_chunks)}/{len(chunk_starts)} "
                                  f"chunks from {partial_path.name}", flush=True)
                except Exception as exc:  # noqa: BLE001
                    print(f"[chunkmajor] partial ignored :: {exc}"[:200], flush=True)
            base_store = data.pandaai_field_store
            shared_index = base_store._index_frame()
            shared_financial = base_store._ensure_financial_cache()
            shared_status = base_store._status_cache
            failures: list[tuple[str, int, str, str, str]] = []
            for chunk_pos, start_at in enumerate(chunk_starts):
                if chunk_pos in done_chunks:
                    continue
                stop_at = min(start_at + span, len(signal_dates))
                first_date, last_date = signal_dates[start_at], signal_dates[stop_at - 1]
                warm_position = max(calendar_positions[first_date] - 800, 0)
                chunk_frame = frame[(frame["date"] >= cal[warm_position])
                                    & (frame["date"] <= last_date)]
                chunk_obj = gp.TushareStockData.from_aligned_frame(
                    frame=chunk_frame, calendar=cal, instrument=stock_ids,
                    start_time=gp.date_text(first_date), end_time=gp.date_text(last_date),
                    max_backtrack_days=756, max_future_days=0, device=device,
                    financial_root=gp.DEFAULT_FINANCIAL_ROOT)
                del chunk_frame
                gc.collect()
                print(f"[chunkmajor] chunk {chunk_pos + 1}/{len(chunk_starts)} start "
                      f"{first_date.date()} rss={_rss_gb():.2f}GB "
                      f"elapsed={time.time() - started:.0f}s", flush=True)
                store = chunk_obj.pandaai_field_store
                store._frame_indexed = shared_index
                store._financial_cache = shared_financial
                store._status_cache = shared_status
                chunk_dates = [pd.Timestamp(value) for value in chunk_obj._evaluation_dates]
                index_of = {date: index for index, date in enumerate(chunk_dates)}
                positions = [index_of[date] for date in signal_dates[start_at:stop_at]]
                for item, key in zip(pending, keys):
                    kind, idx, formula, extra = item
                    expression = None
                    try:
                        expression = gp.evaluate_formula(formula, namespace)
                        with torch.no_grad():
                            values = gp.finite_as_nan(expression.evaluate(chunk_obj))
                        block = values.detach().cpu().numpy()
                        rows[key][start_at:stop_at] = block[positions]
                        del block, values
                    except Exception as exc:  # noqa: BLE001
                        failures.append((kind, idx, extra,
                                         f"{type(exc).__name__}: {exc}", formula))
                    expression = None
                    print(f"[chunkmajor]   {key} rss={_rss_gb():.2f}GB", flush=True)
                del store, chunk_obj
                gc.collect()
                done_chunks.add(chunk_pos)
                np.savez(partial_path,
                         __keys__=np.array(keys),
                         __chunks__=np.array(sorted(done_chunks)),
                         **{key: rows[key] for key in keys})
                print(f"[chunkmajor] chunk {chunk_pos + 1}/{len(chunk_starts)} "
                      f"{first_date.date()}..{last_date.date()} done "
                      f"elapsed={time.time() - started:.0f}s", flush=True)
            failed_keys = {(item[0], item[1]) for item in failures}
            for kind, idx, extra, error, formula in failures:
                with failures_path.open("a", encoding="utf-8") as handle:
                    handle.write(f"{kind}\t{idx}\t{extra}\t{error}\t{formula}\n")
                print(f"  [eval] {kind}_{idx:04d} FAILED :: {error}"[:200], flush=True)
            for item, key in zip(pending, keys):
                kind, idx, formula, extra = item
                if (kind, idx) in failed_keys:
                    continue
                ranks = rank_array(pd.DataFrame(rows[key], index=signal_dates, columns=stock_ids))
                np.save(panel_path(kind, idx), ranks)
                covered = int(np.isfinite(ranks).any(axis=1).sum())
                print(f"  [eval] {kind}_{idx:04d} ok days={covered}/{ranks.shape[0]}", flush=True)
            if partial_path.exists():
                partial_path.unlink()
            print(f"[eval] stage done in {time.time() - started:.0f}s (chunk-major)", flush=True)
            return 0
        print(f"[phase1] member evals shard {shard_index}/{shard_count}: "
              f"{len(todo_members)}/{len(members)}", flush=True)
        for order, idx in enumerate(todo_members, 1):
            row = members.loc[idx]
            if args.skip_heavy_members and args.max_window > 0:
                window = max_rolling_window(str(row["formula"]))
                if window > args.max_window:
                    with skipped_path.open("a", encoding="utf-8") as handle:
                        handle.write(f"member\t{idx}\t{row['name']}\t{window}\t{row['formula']}\n")
                    print(f"[phase1] {order}/{len(todo_members)} member_{idx:04d} SKIPPED window={window}",
                          flush=True)
                    continue
            status = evaluate_into("member", idx, str(row["formula"]), str(row["name"]))
            print(f"[phase1] {order}/{len(todo_members)} member_{idx:04d} {status} "
                  f"elapsed={time.time() - started:.0f}s", flush=True)

        todo_candidates = [] if args.members_only else [
            i for i in candidates.index.tolist() if i % shard_count == shard_index]
        print(f"[phase2] candidate evals shard {shard_index}/{shard_count}: "
              f"{len(todo_candidates)}/{len(candidates)}", flush=True)
        spent = 0.0
        for order, idx in enumerate(todo_candidates, 1):
            row = candidates.loc[idx]
            began = time.time()
            status = evaluate_into("cand", idx, str(row["formula"]), str(row["band"]))
            spent += time.time() - began
            eta_hours = spent / order * (len(todo_candidates) - order) / 3600.0
            print(f"[phase2] {order}/{len(todo_candidates)} cand_{idx:04d} band={row['band']} "
                  f"{status} elapsed={time.time() - started:.0f}s eta={eta_hours:.2f}h", flush=True)

    if args.stage == "eval":
        print(f"[eval] stage done in {time.time() - started:.0f}s", flush=True)
        return 0

    # ------------------------------------------------------------------
    # 阶段 3：逐日横截面 Spearman 相关矩阵（与分簇同口径）
    # ------------------------------------------------------------------
    member_ids = [i for i in members.index.tolist() if panel_path("member", i).exists()]
    cand_ids = [i for i in candidates.index.tolist() if panel_path("cand", i).exists()]
    missing_members = [i for i in members.index.tolist() if i not in set(member_ids)]
    missing_candidates = [i for i in candidates.index.tolist() if i not in set(cand_ids)]
    print(f"[corr] members={len(member_ids)}/{len(members)} candidates={len(cand_ids)}/{len(candidates)} "
          f"missing_members={len(missing_members)} missing_candidates={len(missing_candidates)}", flush=True)
    if not member_ids or not cand_ids:
        print("[corr] nothing to correlate", flush=True)
        return 1

    member_names = [str(members.loc[i, "name"]) for i in member_ids]
    member_matrix = np.stack([np.load(panel_path("member", i)) for i in member_ids]).astype("float32")
    n_members = len(member_ids)
    n_days = int(member_matrix.shape[1])
    cand_meta = candidates.loc[cand_ids].reset_index(drop=True)
    band_labels = [str(value) for value in cand_meta["band"]]

    rho_fast = np.full((len(cand_ids), n_members), np.nan, dtype="float64")
    for start_at in range(0, len(cand_ids), args.chunk):
        stop_at = min(start_at + args.chunk, len(cand_ids))
        cand_block = np.stack([np.load(panel_path("cand", i)) for i in cand_ids[start_at:stop_at]]).astype("float32")
        total = n_members + (stop_at - start_at)
        corr_sum = np.zeros((total, total), dtype="float64")
        corr_cnt = np.zeros((total, total), dtype="float64")
        for day in range(n_days):
            day_matrix = np.concatenate([member_matrix[:, day, :], cand_block[:, day, :]], axis=0)
            accumulate(corr_sum, corr_cnt, day_matrix)
        with np.errstate(invalid="ignore", divide="ignore"):
            block_rho = corr_sum / np.where(corr_cnt > 0.0, corr_cnt, np.nan)
        rho_fast[start_at:stop_at, :] = block_rho[n_members:, :n_members]
        del cand_block
        print(f"[corr] fast chunk {start_at}:{stop_at} elapsed={time.time() - started:.0f}s", flush=True)

    need_exact = np.abs(rho_fast) >= EXACT_FLOOR
    rho_exact = np.full(rho_fast.shape, np.nan, dtype="float64")
    total_pairs = int(need_exact.sum())
    print(f"[corr] exact recheck pairs |rho|>={EXACT_FLOOR}: {total_pairs}", flush=True)
    done_pairs = 0
    for ci, idx in enumerate(cand_ids):
        members_needed = np.flatnonzero(need_exact[ci])
        if not members_needed.size:
            continue
        cand_panel = np.load(panel_path("cand", idx))
        for mi in members_needed.tolist():
            rho_exact[ci, mi] = exact_pair_corr(member_matrix[mi], cand_panel)
            done_pairs += 1
        del cand_panel
        print(f"[corr] exact {done_pairs}/{total_pairs} cand_{idx:04d} elapsed={time.time() - started:.0f}s", flush=True)

    # ------------------------------------------------------------------
    # 阶段 4：输出
    # ------------------------------------------------------------------
    effective = np.where(np.isfinite(rho_exact), rho_exact, rho_fast)
    abs_rho = np.abs(effective)
    filled = np.where(np.isfinite(abs_rho), abs_rho, -1.0)
    best_pos = filled.argmax(axis=1)
    best_val = filled[np.arange(len(cand_ids)), best_pos]
    best_val = np.where(best_val < 0.0, np.nan, best_val)
    hits = (abs_rho >= THRESHOLD).sum(axis=1)
    near_hits = ((abs_rho >= EXACT_FLOOR) & (abs_rho < THRESHOLD)).sum(axis=1)

    cand_labels = [f"cand{idx:04d}" for idx in cand_ids]
    long_frame = pd.DataFrame({
        "candidate": np.repeat(cand_labels, n_members),
        "band": np.repeat(np.array(band_labels, dtype=object), n_members),
        "formula": np.repeat(cand_meta["formula"].astype(str).to_numpy(dtype=object), n_members),
        "member": np.tile(np.array(member_names, dtype=object), len(cand_ids)),
        "member_cluster": np.tile(
            np.array([cluster_map.get(name, UNCLUSTERED) for name in member_names], dtype=object), len(cand_ids)),
        "rho_fast": rho_fast.ravel(),
        "rho_exact": rho_exact.ravel(),
        "rho": effective.ravel(),
    })
    long_frame["abs_rho"] = long_frame["rho"].abs()
    long_path = out_dir / "candidate_member_correlation_long.csv"
    long_frame.to_csv(long_path, index=False, encoding="utf-8")

    wide_frame = pd.DataFrame(effective, index=cand_labels, columns=member_names)
    wide_path = out_dir / "candidate_member_correlation_wide.csv"
    wide_frame.to_csv(wide_path, encoding="utf-8")

    best_names = [member_names[pos] if np.isfinite(val) else "" for pos, val in zip(best_pos, best_val)]
    cluster_hits = []
    top3 = []
    for ci in range(len(cand_ids)):
        ordered = np.argsort(-filled[ci])[:3]
        parts = []
        for mi in ordered.tolist():
            if not np.isfinite(abs_rho[ci, mi]):
                continue
            parts.append(f"{member_names[mi]}:{abs_rho[ci, mi]:.3f}:{cluster_map.get(member_names[mi], UNCLUSTERED)}")
        top3.append(" | ".join(parts))
        clusters = sorted({cluster_map.get(member_names[mi], UNCLUSTERED) for mi in np.flatnonzero(abs_rho[ci] >= THRESHOLD)})
        cluster_hits.append(",".join(clusters))

    matches = cand_meta.copy()
    matches.insert(0, "candidate", cand_labels)
    matches["members_evaluated"] = n_members
    matches["max_abs_corr_member"] = best_val
    matches["max_abs_corr_member_name"] = best_names
    matches["max_abs_corr_member_cluster"] = [
        cluster_map.get(name, UNCLUSTERED) if name else "" for name in best_names]
    matches["members_over_threshold"] = hits
    matches["members_near_threshold"] = near_hits
    matches["clusters_over_threshold"] = cluster_hits
    matches["is_rediscovery"] = hits > 0
    matches["top3"] = top3
    matches_path = out_dir / "candidate_matches.csv"
    matches.to_csv(matches_path, index=False, encoding="utf-8")
    print(f"[out] wrote {long_path.name}, {wide_path.name}, {matches_path.name} "
          f"elapsed={time.time() - started:.0f}s", flush=True)

    # ------------------------------------------------------------------
    # 阶段 5：summary.md
    # ------------------------------------------------------------------
    failure_rows = []
    seen_failure: set[tuple[str, str]] = set()
    for path in sorted(panels_dir.glob("failures_shard*.tsv")):
        for raw in path.read_text(encoding="utf-8").splitlines():
            parts = raw.split("\t")
            if len(parts) < 5:
                continue
            key = (parts[0], parts[1])
            if key in seen_failure:
                continue
            seen_failure.add(key)
            failure_rows.append({"kind": parts[0], "idx": parts[1], "extra": parts[2],
                                 "error": parts[3], "formula": parts[4]})
    missing_cand_ids = {int(value) for value in missing_candidates}
    missing_member_ids = {int(value) for value in missing_members}
    failed_candidates = [row for row in failure_rows
                         if row["kind"] == "cand" and row["idx"].isdigit()
                         and int(row["idx"]) in missing_cand_ids]
    failed_members = [row for row in failure_rows
                      if row["kind"] == "member" and row["idx"].isdigit()
                      and int(row["idx"]) in missing_member_ids]
    failed_fields = sorted({name for row in failed_candidates + failed_members
                            for name in re.findall(r"field ([A-Za-z0-9_]+)", row["error"])})

    band_names = ["40_60", "30_40", "le30", "gt60"]
    band_stats = []
    for band in band_names:
        selected = [ci for ci in range(len(cand_ids)) if band_labels[ci] == band]
        if not selected:
            continue
        values = np.array([best_val[ci] for ci in selected], dtype="float64")
        values = values[np.isfinite(values)]
        band_stats.append({
            "band": band,
            "n": len(selected),
            "rediscovered": int(sum(hits[ci] > 0 for ci in selected)),
            "partial": int(sum((hits[ci] == 0 and near_hits[ci] > 0) for ci in selected)),
            "novel": int(sum((hits[ci] == 0 and near_hits[ci] == 0) for ci in selected)),
            "max": float(values.max()) if values.size else float("nan"),
            "median": float(np.median(values)) if values.size else float("nan"),
        })

    cluster_tally: dict[str, int] = {}
    for ci in range(len(cand_ids)):
        for mi in np.flatnonzero(abs_rho[ci] >= THRESHOLD).tolist():
            label = cluster_map.get(member_names[mi], UNCLUSTERED)
            cluster_tally[label] = cluster_tally.get(label, 0) + 1

    lines = []
    lines.append("# GP 新候选 × 2026-09-19 旧分簇：相关重叠检查")
    lines.append("")
    lines.append(f"- 口径：signal-date 面板 → 按日横截面 Spearman 算术平均；阈值 `|rho| >= {THRESHOLD}`；"
                 f"每日最少 {MIN_PER_DATE} 只股票；窗口 {signal_dates[0].date()} 至 {signal_dates[-1].date()}"
                 f"（{n_days} 个信号日，沪深全 A，qfq + total_mv）")
    lines.append(f"- 快速通道为整日矩阵（同日秩、共同有效集）近似；`|rho| >= {EXACT_FLOOR}` 的配对已用逐日 "
                 f"pairwise-complete 逐对重算（重算 {total_pairs} 对）")
    lines.append(f"- 新候选 {len(cand_ids)}/{len(candidates)} 条成功物化；旧簇成员 {len(member_ids)}/{len(members)} 条成功物化")
    lines.append(
        f"- 簇口径：2026-09-19 all-factor 扩充分簇（B01-B12 / N01-N33），可见复合因子仅注释、不构成簇；未入簇成员命中记作 `{UNCLUSTERED}`")
    if failed_candidates or failed_members:
        all_failed = failed_candidates + failed_members
        field_missing = [row for row in all_failed if re.search(r"field [A-Za-z0-9_]+", row["error"])]
        other_failed = [row for row in all_failed if row not in field_missing]
        lines.append(f"- 未物化：候选 {len(missing_candidates)} 条、成员 {len(missing_members)} 条"
                     f"；其中本地缺字段 {len(field_missing)} 条、"
                     f"本地不支持的平台算子/宏/语法 {len(other_failed)} 条")
        if failed_fields:
            lines.append(f"- 缺失字段：{', '.join(failed_fields)}")
        if other_failed:
            tokens = sorted({match.group(1) for row in other_failed
                             for match in [re.search(r"name '([A-Za-z0-9_]+)'", row["error"])]
                             if match})
            suffix = f"（示例：{', '.join(tokens)}）" if tokens else ""
            lines.append(f"- 本地不支持的平台算子/宏/语法{suffix}；明细见 `panels/failures_shard*.tsv`")
    lines.append("")
    lines.append("## 分档结果")
    lines.append("")
    lines.append("| 换手档 | 条数 | 重发现(任一成员>=0.80) | 部分重叠(0.60-0.80) | 全新(<0.60) | max abs(rho) | 中位 abs(rho) |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for stat in band_stats:
        lines.append(f"| {stat['band']} | {stat['n']} | {stat['rediscovered']} | {stat['partial']} | "
                     f"{stat['novel']} | {stat['max']:.3f} | {stat['median']:.3f} |")
    lines.append("")
    if band_stats:
        top_band = band_stats[0]["band"]
        selected = [ci for ci in range(len(cand_ids)) if band_labels[ci] == top_band][:12]
        lines.append(f"## `{top_band}` 档 Top{len(selected)}（按 net_y2026 降序）")
        lines.append("")
        lines.append("| # | candidate | net | turnover | net_y2026 | corr_size | max abs(rho) | 最近旧成员 | 旧簇 | >=0.80 成员数 |")
        lines.append("| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | ---: |")
        for rank, ci in enumerate(selected, 1):
            row = cand_meta.iloc[ci]
            lines.append(f"| {rank} | {cand_labels[ci]} | {float(row['net']):.4f} | {float(row['turnover']):.4f} | "
                         f"{float(row['net_y2026']):.4f} | {float(row['corr_size']):.3f} | {best_val[ci]:.3f} | "
                         f"{best_names[ci] or '-'} | {cluster_map.get(best_names[ci], UNCLUSTERED) if best_names[ci] else '-'} | "
                         f"{int(hits[ci])} |")
        lines.append("")
        lines.append("候选公式：")
        lines.append("")
        for rank, ci in enumerate(selected, 1):
            lines.append(f"{rank}. `cand{cand_ids[ci]:04d}` `{str(cand_meta.iloc[ci]['formula'])}`")
        lines.append("")

    lines.append("## 旧簇吸并情况")
    lines.append("")
    if cluster_tally:
        lines.append("| 旧簇 | 被命中次数（|rho|>=0.80 的候选×成员对） |")
        lines.append("| --- | ---: |")
        for cluster, count in sorted(cluster_tally.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"| {cluster or '未映射'} | {count} |")
    else:
        lines.append("没有任何新候选与旧簇成员达到 0.80。")
    lines.append("")
    lines.append("## 失败候选（本地缺字段，未参与比较）")
    lines.append("")
    if failed_candidates:
        lines.append("| idx | band | 错误 | 公式 |")
        lines.append("| ---: | --- | --- | --- |")
        for row in failed_candidates:
            lines.append(f"| {row['idx']} | {row['extra']} | {row['error'][:90]} | `{row['formula'][:110]}` |")
    else:
        lines.append("无。")
    lines.append("")
    lines.append("## 结论与局限")
    lines.append("")
    total_rediscovered = sum(stat["rediscovered"] for stat in band_stats)
    total_partial = sum(stat["partial"] for stat in band_stats)
    total_novel = sum(stat["novel"] for stat in band_stats)
    lines.append(f"- 在可物化的 {len(cand_ids)} 条新候选里，{total_rediscovered} 条与至少一个旧簇成员 `|rho| >= 0.80`（重发现），"
                 f"{total_partial} 条落在 0.60-0.80（部分重叠），{total_novel} 条低于 0.60（旧分簇未见）。")
    lines.append("- `rho` 是逐日横截面 Spearman 的信号层相关，不是 PnL 相关；与 2026-09-19 分簇使用同一统计量、同一阈值。")
    lines.append("- 本次未使用平台算力；两侧公式均为本地物化，缺本地 catalog 字段的候选无法参与比较（见上表）。")
    lines.append("")
    summary_path = out_dir / "summary.md"
    summary_path.write_text("\n".join(lines), encoding="utf-8")

    import json as _json
    meta = {
        "rule_version": "cluster-overlap-20260924",
        "generated_at": pd.Timestamp.now().isoformat(),
        "threshold": THRESHOLD,
        "exact_floor": EXACT_FLOOR,
        "min_per_date": MIN_PER_DATE,
        "signal_dates": [d.date().isoformat() for d in signal_dates],
        "window": [signal_dates[0].date().isoformat(), signal_dates[-1].date().isoformat()],
        "cycle": screen.CYCLE,
        "cost": screen.COST,
        "candidates_total": int(len(candidates)),
        "candidates_evaluated": int(len(cand_ids)),
        "members_total": int(len(members)),
        "members_evaluated": int(len(member_ids)),
        "exact_pairs": int(total_pairs),
        "band_stats": band_stats,
        "cluster_tally": cluster_tally,
        "failed_candidates": [row["formula"] for row in failed_candidates],
        "failed_members": [f"{row['extra']} :: {row['formula']}" for row in failed_members],
        "failed_fields": failed_fields,
        "raw_dir": str(out_dir),
    }
    (out_dir / "run_meta.json").write_text(_json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] total {time.time() - started:.0f}s -> {out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
