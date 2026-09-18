#!/usr/bin/env python3
"""Build and query the historical factor-formula exclusion registry.

The registry is deliberately formula based rather than name based.  PandaAI
and AlphaPROBE use different spellings for the same expression, so the
normalizer also handles the common AlphaPROBE function names, commutative
``Add``/``Mul`` trees, unary inverses, and the ``VWAP = AMOUNT / VOLUME``
identity.
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import math
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "research_reports" / "platform_alignment" / "factor_formula_registry.json"
NORMALIZATION_VERSION = "formula-ast-v1-vwap-addmul-inv-aliases"

_FORMULA_KEYS = {
    "formula",
    "panda_formula",
    "best_formula",
    "best_panda_formula",
    "content",
    "expression",
    "factor_formula",
}
_SKIP_DIRS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    ".mypy_cache",
    ".venv",
    "node_modules",
}
_FUNCTION_ALIASES = {
    "ADD": "ADD",
    "SUB": "SUB",
    "MUL": "MUL",
    "DIV": "DIV",
    "INV": "INV",
    "POW": "POW",
    "POWER": "POW",
    "GREATER": "MAX",
    "LESS": "MIN",
    "MAX": "MAX",
    "MIN": "MIN",
    "RANK": "RANK",
    "ABS": "ABS",
    "SIGN": "SIGN",
    "LOG": "LOG",
    "REF": "REF",
    "DELAY": "REF",
    "MA": "MA",
    "TS_MEAN": "MA",
    "SUM": "SUM",
    "TS_SUM": "SUM",
    "STDDEV": "STD",
    "STD": "STD",
    "TS_STD": "STD",
    "VAR": "VAR",
    "TS_VAR": "VAR",
    "TS_SKEW": "SKEW",
    "SKEW": "SKEW",
    "TS_KURT": "KURT",
    "KURT": "KURT",
    "TS_MAX": "MAX_TS",
    "TS_MIN": "MIN_TS",
    "TS_MEDIAN": "MEDIAN",
    "MEDIAN": "MEDIAN",
    "TS_MAD": "MAD",
    "MAD": "MAD",
    "TS_RANK": "RANK_TS",
    "DIFF": "DELTA",
    "TS_DELTA": "DELTA",
    "RETURNS": "PCT_CHANGE",
    "TS_PCT_CHANGE": "PCT_CHANGE",
    "WMA": "WMA",
    "TS_WMA": "WMA",
    "EMA": "EMA",
    "TS_EMA": "EMA",
    "COV": "COV",
    "TS_COV": "COV",
    "COVARIANCE": "COV",
    "CORR": "CORR",
    "TS_CORR": "CORR",
    "CORRELATION": "CORR",
    "TS_DIV": "TS_DIV",
    "TS_IR": "TS_IR",
    "TS_MIN_MAX_DIFF": "TS_MIN_MAX_DIFF",
    "TS_MAX_MIN_DIFF": "TS_MIN_MAX_DIFF",
    "TS_MAX_DIFF": "TS_MAX_DIFF",
    "TS_MIN_DIFF": "TS_MIN_DIFF",
    "SLOG1P": "SLOG1P",
}


def _constant(value: int | float) -> tuple[Any, ...]:
    number = float(value)
    if number == 0.0:
        number = 0.0
    if number.is_integer():
        text = str(int(number))
    else:
        text = format(number, ".15g")
    return ("CONST", text)


def _field(name: str) -> tuple[Any, ...]:
    upper = name.strip().upper()
    if upper in {"VWAP", "$VWAP"}:
        return ("DIV", ("FIELD", "AMOUNT"), ("FIELD", "VOLUME"))
    return ("FIELD", upper.lstrip("$"))


def _make(op: str, *args: tuple[Any, ...]) -> tuple[Any, ...]:
    op = op.upper()
    if op in {"ADD", "MUL", "MAX", "MIN"}:
        flattened: list[tuple[Any, ...]] = []
        for arg in args:
            if arg and arg[0] == op:
                flattened.extend(arg[1:])
            else:
                flattened.append(arg)
        flattened.sort(key=repr)
        if len(flattened) == 1:
            return flattened[0]
        return (op, *flattened)
    if op == "SUB" and len(args) == 2 and args[0] == _constant(0):
        return _make("MUL", _constant(-1), args[1])
    if op == "INV":
        return ("DIV", _constant(1), args[0])
    return (op, *args)


def _call(name: str, args: list[tuple[Any, ...]]) -> tuple[Any, ...]:
    upper = name.upper()
    if upper == "CONSTANT":
        return args[0] if len(args) == 1 else ("CALL", upper, *args)
    if upper == "VWAP" and not args:
        return _field("VWAP")
    op = _FUNCTION_ALIASES.get(upper, upper)
    if op in {"ADD", "SUB", "MUL", "DIV", "POW", "MAX", "MIN"} and len(args) == 2:
        return _make(op, *args)
    if op == "INV" and len(args) == 1:
        return _make("INV", args[0])
    if op == "TS_DIV" and len(args) == 2:
        return _make("DIV", args[0], _call("MA", [args[0], args[1]]))
    if op == "TS_IR" and len(args) == 2:
        return _make("DIV", _call("MA", [args[0], args[1]]), _call("STD", [args[0], args[1]]))
    if op == "TS_MIN_MAX_DIFF" and len(args) == 2:
        return _make("SUB", _call("MAX_TS", [args[0], args[1]]), _call("MIN_TS", [args[0], args[1]]))
    if op == "TS_MAX_DIFF" and len(args) == 2:
        return _make("SUB", args[0], _call("MAX_TS", [args[0], args[1]]))
    if op == "TS_MIN_DIFF" and len(args) == 2:
        return _make("SUB", args[0], _call("MIN_TS", [args[0], args[1]]))
    if op == "SLOG1P" and len(args) == 1:
        arg = args[0]
        return _make("MUL", ("CALL", "SIGN", arg), ("CALL", "LOG", _make("ADD", _constant(1), ("CALL", "ABS", arg))))
    if op in {"MAX_TS", "MIN_TS"} and len(args) == 2:
        # Rolling max/min is idempotent when the same window is applied
        # repeatedly: MAX(MAX(x, n), n) == MAX(x, n).
        inner = args[0]
        if (
            inner
            and inner[0] == "CALL"
            and inner[1] == op
            and len(inner) == 4
            and inner[3] == args[1]
        ):
            return inner
    return ("CALL", op, *args)


def _ast_node(node: ast.AST) -> tuple[Any, ...]:
    if isinstance(node, ast.Name):
        return _field(node.id)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return _constant(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return _make("MUL", _constant(-1), _ast_node(node.operand))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd):
        return _ast_node(node.operand)
    if isinstance(node, ast.BinOp):
        operators = {
            ast.Add: "ADD",
            ast.Sub: "SUB",
            ast.Mult: "MUL",
            ast.Div: "DIV",
            ast.Pow: "POW",
        }
        op = operators.get(type(node.op))
        if op is None:
            raise ValueError(f"unsupported binary operator {type(node.op).__name__}")
        return _make(op, _ast_node(node.left), _ast_node(node.right))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return _call(node.func.id, [_ast_node(arg) for arg in node.args])
    raise ValueError(f"unsupported syntax {type(node).__name__}")


def _render(tree: tuple[Any, ...]) -> str:
    op = tree[0]
    if op in {"FIELD", "CONST"}:
        return str(tree[1])
    if op in {"ADD", "MUL", "MAX", "MIN"}:
        return f"{op}({','.join(_render(item) for item in tree[1:])})"
    if op == "DIV":
        return f"DIV({_render(tree[1])},{_render(tree[2])})"
    if op == "SUB":
        return f"SUB({_render(tree[1])},{_render(tree[2])})"
    if op == "POW":
        return f"POW({_render(tree[1])},{_render(tree[2])})"
    if op == "CALL":
        return f"{tree[1]}({','.join(_render(item) for item in tree[2:])})"
    raise ValueError(f"unknown canonical node {op}")


def normalize_formula(formula: str) -> str | None:
    """Return a stable semantic signature, or ``None`` for non-formula code."""
    text = str(formula).strip()
    if not text or len(text) > 4000 or "class " in text or "def " in text:
        return None
    text = text.replace("$", "")
    text = re.sub(r"\bNaN\b", "0", text, flags=re.IGNORECASE)
    try:
        tree = ast.parse(text, mode="eval")
        return _render(_ast_node(tree.body))
    except (SyntaxError, ValueError, TypeError):
        compact = re.sub(r"\s+", "", text).upper()
        if not re.search(r"[A-Z]", compact):
            return None
        return compact


def _constant_value(tree: tuple[Any, ...]) -> float | None:
    """Evaluate the small constant subtrees emitted by GP expressions."""
    op = tree[0]
    if op == "CONST":
        return float(tree[1])
    if op in {"ADD", "MUL", "MAX", "MIN"}:
        values = [_constant_value(item) for item in tree[1:]]
        if any(value is None for value in values):
            return None
        numbers = [float(value) for value in values]
        if op == "ADD":
            return sum(numbers)
        if op == "MUL":
            result = 1.0
            for number in numbers:
                result *= number
            return result
        return (max if op == "MAX" else min)(numbers)
    if op in {"SUB", "DIV"}:
        left = _constant_value(tree[1])
        right = _constant_value(tree[2])
        if left is None or right is None:
            return None
        if op == "SUB":
            return left - right
        if right == 0.0:
            return None
        return left / right
    if op != "CALL":
        return None

    name = str(tree[1])
    args = tree[2:]
    if name in {"ABS", "SIGN", "LOG"} and len(args) == 1:
        value = _constant_value(args[0])
        if value is None:
            return None
        if name == "ABS":
            return abs(value)
        if name == "SIGN":
            return float(1 if value > 0.0 else -1 if value < 0.0 else 0)
        if value <= 0.0:
            return None
        return float(math.log(value))
    if name in {"MA", "MEDIAN", "WMA", "EMA", "MAX_TS", "MIN_TS"} and len(args) == 2:
        value = _constant_value(args[0])
        window = _constant_value(args[1])
        if value is not None and window is not None:
            return value * window if name == "SUM" else value
    if name == "SUM" and len(args) == 2:
        value = _constant_value(args[0])
        window = _constant_value(args[1])
        if value is not None and window is not None:
            return value * window
    if name in {"STD", "VAR", "SKEW", "KURT", "MAD"} and len(args) >= 1:
        value = _constant_value(args[0])
        if value is not None and all(_constant_value(arg) is not None for arg in args[1:]):
            return 0.0
    return None


def _remove_scalar(tree: tuple[Any, ...]) -> tuple[Any, ...]:
    """Remove non-zero scalar factors while preserving additive structure."""
    op = tree[0]
    if op == "MUL":
        non_constant = []
        for item in tree[1:]:
            if _constant_value(item) is None:
                non_constant.append(_remove_scalar(item))
        if len(non_constant) == 1:
            return non_constant[0]
        if non_constant:
            return _make("MUL", *non_constant)
        return tree
    if op == "DIV":
        numerator, denominator = tree[1], tree[2]
        denominator_value = _constant_value(denominator)
        if denominator_value is not None and denominator_value != 0.0:
            return _remove_scalar(numerator)
        numerator = _remove_scalar(numerator)
        if _constant_value(numerator) not in {None, 0.0}:
            # 1/x and -1/x are the same rank signal after direction selection.
            numerator = _constant(1)
        return _make("DIV", numerator, _remove_scalar(denominator))
    return tree


def _monomial_parts(tree: tuple[Any, ...]) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    """Flatten multiplication/division chains for algebraic duplicate checks."""
    op = tree[0]
    if op == "MUL":
        numerators: list[tuple[Any, ...]] = []
        denominators: list[tuple[Any, ...]] = []
        for item in tree[1:]:
            numerator, denominator = _monomial_parts(item)
            numerators.extend(numerator)
            denominators.extend(denominator)
        return numerators, denominators
    if op == "DIV":
        left_numerator, left_denominator = _monomial_parts(tree[1])
        right_numerator, right_denominator = _monomial_parts(tree[2])
        return left_numerator + right_denominator, left_denominator + right_numerator
    return [tree], []


def normalize_scale_invariant_formula(formula: str) -> str | None:
    """Return a rank-signal signature invariant to non-zero scalar factors.

    Formula direction is selected separately on PandaAI, so ``x`` and ``-2*x``
    are the same factor for historical-duplicate purposes.  This deliberately
    only removes scalar factors from multiplicative/divisive chains; additive
    constants and additive combinations remain distinct.
    """
    text = str(formula).strip()
    if not text or len(text) > 4000 or "class " in text or "def " in text:
        return None
    text = text.replace("$", "")
    text = re.sub(r"\bNaN\b", "0", text, flags=re.IGNORECASE)
    try:
        tree = _ast_node(ast.parse(text, mode="eval").body)
    except (SyntaxError, ValueError, TypeError):
        return None
    tree = _remove_scalar(tree)
    numerators, denominators = _monomial_parts(tree)
    numerators.sort(key=repr)
    denominators.sort(key=repr)
    if len(numerators) == 1:
        numerator = numerators[0]
    else:
        numerator = _make("MUL", *numerators)
    if not denominators:
        return _render(numerator)
    if len(denominators) == 1:
        denominator = denominators[0]
    else:
        denominator = _make("MUL", *denominators)
    return _render(_make("DIV", numerator, denominator))


def load_scale_invariant_signatures(path: Path) -> set[str]:
    """Load scale-invariant signatures from a formula registry."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    signatures = set()
    for item in payload.get("formulas", []):
        signature = normalize_scale_invariant_formula(item.get("representative_formula", ""))
        if signature is not None:
            signatures.add(signature)
    return signatures


def _formula_from_candidate_line(line: str) -> str | None:
    if "~" not in line or line.lstrip().startswith("#"):
        return None
    parts = line.split("~")
    if len(parts) < 3:
        return None
    formula = parts[1].strip()
    return formula or None


def _record(records: list[dict[str, Any]], formula: str, source: str, kind: str) -> None:
    signature = normalize_formula(formula)
    if signature is None:
        return
    records.append(
        {
            "formula": str(formula).strip(),
            "signature": signature,
            "source": source,
            "kind": kind,
        }
    )


def _walk_formula_keys(value: Any, path: str, records: list[dict[str, Any]], source: str) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key).lower()
            child_path = f"{path}/{key}"
            if key_text in _FORMULA_KEYS and isinstance(child, str):
                _record(records, child, f"{source}:{child_path}", "structured")
            elif key_text == "cache" and isinstance(child, dict):
                for formula in child:
                    if isinstance(formula, str):
                        _record(records, formula, f"{source}:{child_path}", "gp-cache")
            _walk_formula_keys(child, child_path, records, source)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_formula_keys(child, f"{path}/{index}", records, source)


def _collect_text_file(path: Path, records: list[dict[str, Any]]) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return
    for line_number, line in enumerate(text.splitlines(), start=1):
        formula = _formula_from_candidate_line(line)
        if formula:
            _record(records, formula, f"{path.relative_to(PROJECT_ROOT)}:{line_number}", "candidate-file")


def _collect_csv(path: Path, records: list[dict[str, Any]]) -> None:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                return
            keys = [key for key in reader.fieldnames if key and key.lower() in _FORMULA_KEYS]
            if not keys:
                return
            for row_number, row in enumerate(reader, start=2):
                for key in keys:
                    value = row.get(key)
                    if value:
                        _record(records, value, f"{path.relative_to(PROJECT_ROOT)}:{row_number}/{key}", "csv")
    except (OSError, UnicodeDecodeError, csv.Error):
        return


def _iter_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file() or any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.name == DEFAULT_OUTPUT.name:
            continue
        if any(part == ".quantlab" for part in path.parts) and "reports" not in path.parts:
            continue
        if path.suffix.lower() in {".parquet", ".feather", ".png", ".jpg", ".tar", ".gz", ".pyc"}:
            continue
        yield path


def collect_records(root: Path = PROJECT_ROOT) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in _iter_files(root):
        relative = path.relative_to(root)
        suffix = path.suffix.lower()
        name = path.name.lower()
        if suffix == ".json":
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            _walk_formula_keys(payload, "", records, str(relative))
        elif suffix == ".csv":
            _collect_csv(path, records)
        elif suffix in {".txt", ".md", ".formula"} and (
            "candidate" in name
            or "workflow" in name
            or name.endswith(".formula")
            or "factor" in name
        ):
            _collect_text_file(path, records)
    return records


def build_registry(root: Path, output: Path) -> dict[str, Any]:
    records = collect_records(root)
    grouped: dict[str, dict[str, Any]] = {}
    for record in records:
        group = grouped.setdefault(
            record["signature"],
            {
                "signature": record["signature"],
                "representative_formula": record["formula"],
                "sources": [],
                "kinds": [],
            },
        )
        source = {"formula": record["formula"], "source": record["source"], "kind": record["kind"]}
        if source not in group["sources"]:
            group["sources"].append(source)
        if record["kind"] not in group["kinds"]:
            group["kinds"].append(record["kind"])
    groups = sorted(grouped.values(), key=lambda item: item["signature"])
    for group in groups:
        group["sources"].sort(key=lambda item: (item["source"], item["formula"]))
    payload = {
        "schema_version": 1,
        "normalization_version": NORMALIZATION_VERSION,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "summary": {
            "raw_records": len(records),
            "unique_signatures": len(groups),
            "candidate_file_records": sum(item["kind"] == "candidate-file" for item in records),
            "platform_structured_records": sum(item["kind"] == "structured" for item in records),
            "gp_cache_records": sum(item["kind"] == "gp-cache" for item in records),
        },
        "formulas": groups,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def load_signatures(path: Path) -> set[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {str(item["signature"]) for item in payload.get("formulas", [])}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--root", type=Path, default=PROJECT_ROOT)
    build.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    check = subparsers.add_parser("check")
    check.add_argument("formula")
    check.add_argument("--registry", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.command == "build":
        payload = build_registry(args.root.resolve(), args.output.resolve())
        print(json.dumps(payload["summary"], ensure_ascii=False))
        return 0
    signature = normalize_formula(args.formula)
    if signature is None:
        print("invalid-formula")
        return 2
    signatures = load_signatures(args.registry.resolve())
    print(json.dumps({"signature": signature, "existing": signature in signatures}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
