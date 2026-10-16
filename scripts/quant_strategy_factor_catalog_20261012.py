#!/usr/bin/env python3
"""Read and index the strategy corpus under ``quant``.

This is deliberately an inventory pass: it never runs a platform backtest and
never treats a strategy headline as a validated factor.  Every source file is
 represented in the machine-readable index. Field fingerprints are navigation
 labels, not evidence of independent mechanisms or statistical clusters.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "quant"
DEFAULT_OUTPUT = ROOT / "research_reports" / "literature" / "quant-corpus-factor-catalog-20261012"

EXTENSIONS = {".txt", ".py", ".ipynb"}
KEYWORDS: dict[str, tuple[str, ...]] = {
    "momentum_reversal": ("动量", "反转", "momentum", "reversal", "returns", "ret_20"),
    "value": ("估值", "价值", "PB", "PE", "PS", "PCF", "book_to", "市净", "市盈"),
    "quality": ("ROE", "ROA", "ROIC", "EBIT", "EBITDA", "FScore", "质量", "盈利"),
    "growth": ("成长", "增长", "PEG", "研发", "revenue", "净利润同比", "营收"),
    "size": ("市值", "小市值", "大市值", "market_cap", "circulating_market_cap"),
    "volatility": ("波动", "volatility", "std", "特质波动", "低波"),
    "turnover": ("换手", "turnover", "流动性", "成交量", "成交额", "amount", "volume"),
    "price_volume": ("价量", "量价", "相关性", "corr", "covariance", "VWAP", "OBV"),
    "intraday": ("分钟", "日内", "tick", "开盘", "收盘", "open", "intraday", "overnight"),
    "technical": ("MACD", "RSI", "KDJ", "布林", "RSRS", "均线", "ATR", "海龟"),
    "event_short": ("涨停", "打板", "首板", "二板", "竞价", "龙虎榜", "龙头"),
    "etf_macro": ("ETF", "宏观", "指数", "行业轮动", "择时", "期货", "期权"),
    "machine_learning": ("机器学习", "XGBoost", "LightGBM", "随机森林", "SVM", "LSTM", "神经网络"),
}

# Short English tokens are only accepted as standalone identifiers.  This
# prevents ordinary code words such as ``open``/``append`` from turning every
# JoinQuant script into an intraday factor candidate.
WORD_ONLY = {
    "ROE", "ROA", "ROIC", "EBIT", "EBITDA", "PB", "PE", "PS", "VWAP", "OBV",
    "MACD", "RSI", "KDJ", "RSRS", "ETF", "LSTM", "SVM", "AMOUNT", "VOLUME",
    "TURNOVER", "MOMENTUM", "REVERSAL", "FACTOR", "ALPHA",
}

FORMULA_HINTS = (
    r"(?:factor|fac(?:tor)?[_A-Za-z0-9]*|score|alpha|signal|因子)\s*[=:]",
    r"(?:rank|RANK|rolling|rolling_mean|pct_change|std|corr|cov|mean|TS_[A-Z]+)\s*\(",
    r"(?:RETURNS|CLOSE|OPEN|HIGH|LOW|VOLUME|AMOUNT|TURNOVER|ROE|ROA|EBIT|EV|PB|PE)",
)


def read_text(path: Path) -> str:
    if path.suffix.lower() == '.ipynb':
        notebook = json.loads(path.read_text(encoding='utf-8-sig'))
        return '\n\n'.join(''.join(c.get('source', [])) for c in notebook['cells'])
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "gb18030", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise UnicodeError(f'Cannot decode source: {path}')


def title(path: Path, text: str) -> str:
    for line in text.splitlines()[:80]:
        if line.startswith('#!'):
            continue
        clean = re.sub(r"^[#\s/*\-]+", "", line).strip()
        if clean and "标题" in clean:
            clean = re.sub(r"^(标题\s*[:：])", "", clean).strip()
            if len(clean) > 4:
                return clean[:180]
    return path.stem


def evidence(text: str, tags: list[str]) -> list[str]:
    rows: list[str] = []
    needles = []
    for tag in tags:
        needles.extend(KEYWORDS[tag])
    pattern = re.compile("|".join(re.escape(x) for x in sorted(set(needles), key=len, reverse=True)), re.I)
    for raw in text.splitlines():
        line = raw.strip()
        if not line or len(line) > 320:
            continue
        if pattern.search(line) and ("=" in line or "：" in line or "公式" in line or "因子" in line or "计算" in line):
            rows.append(re.sub(r"\s+", " ", line))
        if len(rows) >= 8:
            break
    return rows


def classify(text: str) -> tuple[list[str], list[str], str]:
    folded = text.lower()
    def has_word(word: str) -> bool:
        if word.upper() in WORD_ONLY:
            return re.search(r"(?<![A-Za-z0-9_])" + re.escape(word) + r"(?![A-Za-z0-9_])", text, re.I) is not None
        return word.lower() in folded
    tags = [tag for tag, words in KEYWORDS.items() if any(has_word(word) for word in words)]
    deps: list[str] = []
    if any(x in folded for x in ("分钟", "tick", "日内高频", "1min", "半小时")):
        deps.append("intraday_data")
    if any(x in folded for x in ("资金流", "龙虎榜", "北向", "主力资金", "大单")):
        deps.append("money_flow_or_event")
    if any(has_word(x) for x in ("财务", "ROE", "ROA", "EBIT", "营业利润", "净利润", "现金流", "PB", "PE")):
        deps.append("pit_financial_or_valuation")
    if any(x in folded for x in ("行业", "概念", "申万", "板块")):
        deps.append("industry_or_concept")
    if any(x in folded for x in ("期货", "期权", "etf", "基金")):
        deps.append("non_stock_asset")
    if any(x in folded for x in ("机器学习", "xgboost", "lightgbm", "随机森林", "svm", "lstm")):
        deps.append("model_training")
    if not deps:
        deps.append("daily_stock_fields")
    if "intraday_data" in deps or "money_flow_or_event" in deps or "non_stock_asset" in deps:
        status = "diagnostic_only_or_unavailable"
    elif "model_training" in deps:
        status = "model_recipe_requires_rebuild"
    elif "pit_financial_or_valuation" in deps:
        status = "candidate_if_field_mapping_exists"
    else:
        status = "candidate_for_daily_local_reproduction"
    return sorted(set(tags)), sorted(set(deps)), status


def mechanism_fingerprint(tags: list[str], deps: list[str], text: str) -> str:
    tokens = []
    for key in ("RETURNS", "CLOSE", "OPEN", "HIGH", "LOW", "VOLUME", "AMOUNT", "TURNOVER", "ROE", "ROA", "EBIT", "EBITDA", "PB", "PE", "PS", "RSI", "MACD", "RSRS", "FScore", "corr", "std", "rank"):
        if re.search(re.escape(key), text, re.I):
            tokens.append(key.lower())
    raw = "|".join(tags) + "::" + "|".join(deps) + "::" + "|".join(sorted(set(tokens)))
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def scan(source: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(p for p in source.rglob("*") if p.is_file()):
        readable = path.suffix.lower() in EXTENSIONS
        text = read_text(path) if readable else ''
        tags, deps, status = classify(text)
        if not readable:
            status = 'unreadable_proprietary_binary' if path.suffix.lower() == '.rzrk' else 'supporting_asset'
            tags, deps = [], []
        hints = [line for line in text.splitlines() if any(re.search(p, line, re.I) for p in FORMULA_HINTS)]
        rows.append({
            "path": str(path.relative_to(ROOT)),
            "bytes": path.stat().st_size,
            "title": title(path, text),
            "tags": ";".join(tags),
            "dependencies": ";".join(deps),
            "status": status,
            "review_level": 'source_evidence_indexed' if readable else 'not_strategy_text',
            "formula_hint_count": len(hints),
            "evidence": " || ".join(evidence(text, tags)),
            "mechanism_fingerprint": mechanism_fingerprint(tags, deps, text),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    return rows


def write(rows: list[dict[str, Any]], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else []
    with (output / "source_inventory.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)
    (output / "source_inventory.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(row["mechanism_fingerprint"], []).append(row)
    summary = [
        "# quant 策略库因子阅读索引",
        "",
        f"文件总数：{len(rows)}；可解码文本：{sum(Path(r['path']).suffix in EXTENSIONS for r in rows)}。每个源文件均保留在 `source_inventory.csv/json`。",
        '索引程序读取全部可解码文本并提取证据，但不等同于逐行人工语义审阅。字段指纹仅用于导航，不是独立因子或相关性簇。rzrk 是不透明二进制，不能宣称已阅读。',
        '',
        '本地92项因子/对照的五年、近期测试及旧簇相关性见[复现报告](../../platform_alignment/quant-corpus-source-reproduction-20261012/summary.md)。逐文件阅读层级见[source_review.csv](source_review.csv)，尚未复现字段见[unreproduced_field_recipes.csv](unreproduced_field_recipes.csv)。',
        "",
        "## 状态统计",
        "",
    ]
    for key, count in sorted({k: sum(r["status"] == k for r in rows) for k in {r["status"] for r in rows}}.items(), key=lambda x: (-x[1], x[0])):
        summary.append(f"- `{key}`：{count}")
    summary += ["", "## 字段导航（不能作为统计分簇）", "", "| fingerprint | files | tags | dependencies | examples |", "|---|---:|---|---|---|"]
    for key, members in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        summary.append("| {} | {} | {} | {} | {} |".format(key, len(members), members[0]["tags"], members[0]["dependencies"], "；".join(m["path"] for m in members[:3])))
    (output / "summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    rows = scan(args.source)
    write(rows, args.output)
    print(f"indexed={len(rows)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
