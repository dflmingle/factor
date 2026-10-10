# -*- coding: utf-8 -*-
"""提交前"同式复发"检查（2026-10-09）：候选公式是否与仓库里已提交过的候选同款。

背景：2026-10-09 的 POOL6-CAND-C-20261009 与 2026-09-29 的 LAMD10-K5V2-20260929
是同一因子（同腿集、等权），只是名字不同、写法不同（`(...) / 5` vs `0.2*RANK(...)`），
说明此前没有对"历史已测公式"做去重。

判定口径（保守）：
- 若公式含 RANK(...) 顶层等权复合，则取"腿集合"（RANK 参数的规范化文本，排序后）+ 腿数；
  两条候选腿集合相同即判为同式（等权合成下与权重写法无关）。
- 否则退化为整式规范化文本比对。
规范化：去空白；反复剥掉"多余括号"（括号对整体包裹、且前面是运算符/左括号/行首、
  后面是右括号/逗号/运算符/行尾）。

用法:
    python scripts/dup_formula_check.py                 # 扫描全仓历史候选文件
    python scripts/dup_formula_check.py <candidates.txt> [<...>]   # 只检查指定文件
零平台算力，纯本地。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {".git", "node_modules", ".venv", "__pycache__", "quantlab", ".quantlab"}


def strip_space(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _matching_close(text: str, i: int) -> int:
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "(":
            depth += 1
        elif text[j] == ")":
            depth -= 1
            if depth == 0:
                return j
    return -1


def unwrap(text: str) -> str:
    """反复剥掉多余括号。"""
    out = strip_space(text)
    changed = True
    while changed:
        changed = False
        for i, ch in enumerate(out):
            if ch != "(":
                continue
            j = _matching_close(out, i)
            if j < 0:
                break
            prev = out[i - 1] if i else ""
            nxt = out[j + 1] if j + 1 < len(out) else ""
            ok_prev = prev == "" or prev in "(-+*/,<>="
            ok_next = nxt == "" or nxt in ")-+*/,<>="
            if ok_prev and ok_next:
                out = out[:i] + out[i + 1:j] + out[j + 1:]
                changed = True
                break
    return out


def rank_legs(formula: str) -> list[str] | None:
    """抽取顶层 RANK(...) 的腿（按括号配对切分）。"""
    text = strip_space(formula)
    legs: list[str] = []
    i = 0
    while True:
        m = re.search(r"\bRANK\s*\(", text[i:], flags=re.I)
        if not m:
            break
        start = i + m.end() - 1
        j = _matching_close(text, start)
        if j < 0:
            return None
        legs.append(unwrap(text[start + 1:j]))
        i = j + 1
    return legs or None


def canonical(formula: str) -> str:
    legs = rank_legs(formula)
    if legs:
        return f"LEGS[{len(legs)}]:" + "|".join(sorted(legs))
    return "EXPR:" + unwrap(formula)


def parse_candidates(path: Path):
    out = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8-sig", errors="replace").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("~")]
        if len(parts) < 2:
            continue
        try:
            shown = str(path.resolve().relative_to(ROOT))
        except ValueError:
            shown = str(path)
        out.append({"name": parts[0], "formula": parts[1], "file": shown, "line": lineno})
    return out


def iter_candidate_files(extra: list[Path]):
    seen = set()
    for path in list(extra):
        if path.is_file():
            seen.add(path.resolve())
    patterns = ["research_reports/**/candidates*.txt", "*-candidates.txt", "candidates*.txt"]
    for pattern in patterns:
        for path in ROOT.glob(pattern):
            if any(part in SKIP_PARTS for part in path.parts) or not path.is_file():
                continue
            seen.add(path.resolve())
    return sorted(seen)


def main() -> int:
    extra = [Path(a) for a in sys.argv[1:]]
    files = iter_candidate_files(extra)
    rows = []
    for path in files:
        try:
            rows.extend(parse_candidates(path))
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] {path}: {exc}")
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(canonical(row["formula"]), []).append(row)
    dupes = {k: v for k, v in groups.items() if len(v) >= 2}
    print(f"扫描候选文件 {len(files)} 个，候选 {len(rows)} 条，同式组 {len(dupes)} 个")
    for key, items in sorted(dupes.items(), key=lambda kv: -len(kv[1])):
        names = {it['name'] for it in items}
        if len(names) == 1 and len(items) > 1:
            continue  # 同名重复出现（多次重跑）不算
        print(f"\n[同式] {key[:160]}")
        for it in items:
            print(f"    {it['name']:42s} {it['file']}:{it['line']}")
    probes = [Path(p) for p in extra]
    if probes:
        probe_rows = [r for f in probes if f.is_file() for r in parse_candidates(f)]
        for row in probe_rows:
            key = canonical(row["formula"])
            hits = [h for h in groups.get(key, []) if h["file"] != row["file"]]
            print(f"\n检查 {row['name']}: {'同式 ' + str(len(hits)) + ' 处' if hits else '无历史同式'}")
            for hit in hits:
                print(f"    -> {hit['name']:42s} {hit['file']}:{hit['line']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
