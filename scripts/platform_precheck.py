"""提交前静态流水线：撞名预检 + 量级估算 + 脆弱结构标记 + 费用预估。

用法:
    python scripts/platform_precheck.py <candidates_file> [--direction-from-file]
候选文件格式（与提交器一致）：name ~ formula ~ direction
"""
import io, sys, re, ast, math
from pathlib import Path

# --- 2026-09-25 扩展：分母含"有符号/近零"字段（不限于 corr）-----------------
# 证据：K020（corr/MA(corr)）、K029（ASI/MA(ASI,20)）、K031（BBIBOLL_DOWN）三例平台端
# 均出现"方向翻转 + 换手膨胀"，本地不可复现。
SIGNED_DIVISOR_FIELDS = {
    "bbiboll_down", "bbiboll_up", "bbi", "asi", "asit",
    "dpo", "roc", "trix", "macd_dif", "macd_dea",
    "cci", "bias", "mtm", "adtm", "maadtm", "ddi", "diz",
}


def _leaves(node: ast.AST) -> list[str]:
    out = []
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            out.append(n.id)
    return out


def _signed_in(node: ast.AST) -> list[str]:
    return sorted({n for n in _leaves(node) if n.lower() in SIGNED_DIVISOR_FIELDS})


def corr_in_denominator(tree: ast.AST) -> list[str]:  # noqa: F811 - 覆盖上文旧实现
    """标记脆弱分母：相关系数 + 有符号/近零字段（BBIBOLL_DOWN、ASI/MA(ASI) 等）。"""
    tags = []
    for node in ast.walk(tree):
        dens: list[ast.AST] = []
        if isinstance(node, ast.Call) and getattr(node.func, "id", "").upper() in {"DIV", "TSDIV"} and len(node.args) == 2:
            dens.append(node.args[1])
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            dens.append(node.right)
        for den in dens:
            signed = _signed_in(den)
            if signed:
                tags.append("signed_divisor:" + "|".join(signed))
            if not _contains_corr(den):
                continue
            fname = getattr(getattr(den, "func", None), "id", "").upper() if isinstance(den, ast.Call) else ""
            if isinstance(den, ast.BinOp) and isinstance(den.op, ast.Div) and _is_ma_of(den.right, den.left):
                tags.append("corr_over_ma")
            elif fname in {"TSDIV"}:
                tags.append("corr_over_ma")
            elif isinstance(den, ast.Name):
                tags.append("raw_corr_divisor")
            else:
                tags.append("corr_inside_expr")
    return sorted(set(tags))


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
OPS_MD = ROOT / "vendor" / "skill-pandaai-factor-online" / "references" / "operators.md"

CORR_OPS = {"TsCorr", "Corr", "TsCov", "Cov", "CORR", "COV"}

# 字段量级表（元 / 手 / 比例），来源：本地缓存抽样（2026-09-25）
FIELD_MAG = {
    "amount": 1e8, "amcal_20d_amt_ma": 1e8, "cal_20d_amt_ma": 1e8,
    "bs_total_assets": 4e9, "total_assets": 4e9, "bs_total_liab": 2e9,
    "a_share_market_val": 1e10, "market_cap": 1e10, "total_mv": 1e10, "circ_mv": 4e9,
    "close": 15.0, "open": 15.0, "high": 15.0, "low": 15.0, "open_": 15.0,
    "volume": 8e4, "vol": 8e4,
    "turnover": 0.03, "qtyr_5_20": 1.0, "ratio_bm_lyr": 0.5, "ratio_bm_ttm": 0.5,
    "davol5": 1.0, "davol10": 1.0, "davol20": 1.0,
    "asi": 1e2, "vma3": 15.0, "macd_diff": 0.1, "atr": 1.0,
}
DEFAULT_FIELD_MAG = 1.0
SCALE_TARGET = 0.1        # 归一目标量级
CORR_FIELD_MAG = 0.1


def load_platform_ops() -> set[str]:
    text = OPS_MD.read_text(encoding="utf-8")
    ops = {m.group(1).lower() for m in re.finditer(r"\|\s*`?([A-Z][A-Z0-9_]{1,24})\s*\(", text)}
    ops |= {m.group(1).lower() for m in re.finditer(r"`([A-Za-z][A-Za-z0-9_]{1,24})\(", text)}
    return ops


def field_mag(name: str) -> float:
    low = name.lower()
    if "corr" in low:
        return CORR_FIELD_MAG
    return FIELD_MAG.get(low, DEFAULT_FIELD_MAG)


def estimate(tree: ast.AST) -> float:
    """粗略数量级估计（同一量级内不追求精度，只用于选 10^k）。"""
    if isinstance(tree, ast.Expression):
        return estimate(tree.body)
    if isinstance(tree, ast.Constant) and isinstance(tree.value, (int, float)):
        return abs(float(tree.value)) or 1.0
    if isinstance(tree, ast.Name):
        return field_mag(tree.id)
    if isinstance(tree, ast.UnaryOp):
        return estimate(tree.operand)
    if isinstance(tree, ast.BinOp):
        left, right = estimate(tree.left), estimate(tree.right)
        if isinstance(tree.op, ast.Mult): return left * right
        if isinstance(tree.op, ast.Div): return left / right if right else 1.0
        if isinstance(tree.op, (ast.Add, ast.Sub)): return max(left, right)
        if isinstance(tree.op, ast.Pow): return left ** float(getattr(tree.right, "value", 1) or 1)
        return max(left, right)
    if isinstance(tree, ast.Call):
        fn = getattr(tree.func, "id", "")
        up = fn.upper()
        args = [estimate(a) for a in tree.args]
        if up in {"CORR", "COV", "TSCORR", "TSCOV"}: return CORR_FIELD_MAG
        if up in {"POWER", "POW"}: return args[0] ** args[1]
        if up in {"INV"}: return 1.0 / args[0] if args and args[0] else 1.0
        if up in {"DIV"} and len(args) == 2: return args[0] / args[1] if args[1] else 1.0
        if up in {"MUL"} and len(args) == 2: return args[0] * args[1]
        if up in {"SUB", "ADD"} and len(args) == 2: return max(args)
        if up in {"TSRANK", "RANK", "ABS", "SIGN", "LOG", "SLOG1P"}: return 1.0 if up in {"TSRANK","RANK","SIGN"} else (args[0] if args else 1.0)
        if args and up in {"MA", "TS_MEAN", "EMA", "TSEMA", "STDDEV", "TS_STD", "SUM", "TSSUM", "REF",
                           "TS_MAX", "TS_MIN", "TS_MEDIAN", "TS_MAD", "WMA", "TSWMA", "DIFF", "TSDELTA",
                           "RETURNS", "TSPCTCHANGE", "VAR", "TSVAR", "TS_SKEW", "TS_KURT", "TSMAX", "TSMIN",
                           "TSMEAN", "TSSUM", "TSSTD", "TSVAR", "TSMED", "TSMAD", "TSDELTA", "TSPCTCHANGE"}:
            return args[0]
        if args: return args[0]
        return 1.0
    return 1.0


def _contains_corr(node: ast.AST) -> bool:
    return any((isinstance(n, ast.Call) and getattr(n.func, "id", "") in CORR_OPS)
               or (isinstance(n, ast.Name) and "corr" in n.id.lower()) for n in ast.walk(node))


def _is_ma_of(node: ast.AST, inner: ast.AST) -> bool:
    """判断 node 是否为 inner 的滚动均值（MA(X,N) 或 TS_MEAN(X,N)）。"""
    if not isinstance(node, ast.Call):
        return False
    if getattr(node.func, "id", "").upper() not in {"MA", "TS_MEAN", "TSMEAN", "MEAN"}:
        return False
    if not node.args:
        return False
    return ast.dump(node.args[0]) == ast.dump(inner)


def analyze(name: str, formula: str, platform_ops: set[str]) -> dict:
    tree = ast.parse(formula, mode="eval")
    called = {getattr(n.func, "id", "").lower() for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    bare = {n.id.lower() for n in ast.walk(tree) if isinstance(n, ast.Name)}
    bare -= called
    collisions = sorted(t for t in bare if t in platform_ops)
    frag = corr_in_denominator(tree)
    est = estimate(tree)
    k = 0
    if est > 0:
        k = int(round(-1 - math.log10(est)))
        k = max(0, min(40, k))
    needs_scale = est < 1e-6 or est > 1e6
    n_fields = len([t for t in bare if not t.isdigit()])
    cost = 2.0 if (n_fields <= 1 and not called) else 4.0
    return dict(name=name, formula=formula, collisions=collisions, fragile=frag, est=est, k=k,
                needs_scale=needs_scale, cost=cost, n_ops=len(called))


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__); return 2
    path = Path(args[0])
    ops = load_platform_ops()
    print(f"候选文件: {path}")
    print(f"平台算子名: {len(ops)}\n")
    rows = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"): continue
        parts = [p.strip() for p in line.split("~")]
        name, formula = parts[0], parts[1]
        direction = parts[2] if len(parts) > 2 else "?"
        rows.append(analyze(name, formula, ops) | {"direction": direction})
    print(f"{'cand':30s} {'撞名':>6s} {'脆弱':>6s} {'估计量级':>10s} {'建议k':>6s} {'费用':>5s}  备注")
    for r in rows:
        note = []
        if r["needs_scale"]:
            note.append(f"需前置 POWER(10,{r['k']})")
        if r["fragile"]:
            note.append("方向必须实测")
        print(f"{r['name']:30s} {('有' if r['collisions'] else '无'):>6s} "
              f"{('有' if r['fragile'] else '无'):>6s} {r['est']:>10.3g} {r['k']:>6d} {r['cost']:>5.1f}  {'; '.join(note)}")
        if r["collisions"]:
            print(f"     ⚠ 裸字段与平台算子撞名: {r['collisions']} → 改用算子形式或换字段")
        if r["fragile"]:
            print(f"     ⚠ 分母含相关系数/有符号近零字段（{','.join(r['fragile'])}）→ 平台排序/方向不可预测，优先替换、方向必须实测")
    total = sum(r["cost"] for r in rows)
    print(f"\n预估费用: {total:.1f} 算力（{len(rows)} 条）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
