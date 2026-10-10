"""提交前静态流水线：撞名预检 + 量级估算 + 脆弱结构标记 + 费用预估。

用法:
    python scripts/platform_precheck.py <candidates_file> [--direction-from-file]
候选文件格式（与提交器一致）：name ~ formula ~ direction
"""
import io, sys, re, ast, math, builtins, tokenize
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


def board_collision(name: str, board_names: set[str], board_norm: dict[str, set[str]]) -> list[str]:
    """因子展示名与榜单席位名的撞名检查（2026-10-08：提交名前必须清单）。"""
    if not board_names:
        return []
    hits: list[str] = []
    if name in board_names:
        hits.append("原样与榜单席位名相同")
    from board_name_guard import normalize  # 同目录脚本
    fuzzy = sorted(board_norm.get(normalize(name), set()) - {name})
    if fuzzy:
        hits.append("归一化后与榜单重名: " + "|".join(fuzzy[:3]))
    return hits


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

# 本地 GP 名 -> 平台算子名的建议映射（教训：2026-09-29 VV6_1250 首次提交因 TSSTD 不在平台而失败）
LOCAL_TS_ALIASES = {
    "tsstd": "STDDEV", "tsstddev": "STDDEV", "tsmean": "MA / TS_MEAN", "tsmax": "TS_MAX",
    "tsmin": "TS_MIN", "tssum": "SUM", "tsvar": "VAR", "tsmed": "TS_MEDIAN", "tsmad": "TS_MAD",
    "tsdelta": "DELTA", "tspctchange": "PCT_CHANGE", "tscorr": "CORR", "tscov": "COV",
    "tsrank": "TS_RANK", "tsema": "EMA", "tswma": "WMA", "tskurt": "TS_KURT",
}


def load_platform_ops() -> set[str]:
    text = OPS_MD.read_text(encoding="utf-8")
    ops = {m.group(1).lower() for m in re.finditer(r"\|\s*`?([A-Z][A-Z0-9_]{1,24})\s*\(", text)}
    ops |= {m.group(1).lower() for m in re.finditer(r"`([A-Za-z][A-Za-z0-9_]{1,24})\(", text)}
    return ops


# 公式模式基础字段（2026-09-29 教训：VWAP 不在平台字段表 -> "Missing required base factors"）
BASE_FIELDS = {"open", "close", "high", "low", "volume", "amount", "turnover", "market_cap"}
FIELD_DOC_PATTERNS = ("fields*.md",)


def load_known_fields() -> set[str]:
    known = set(BASE_FIELDS)
    ref_dir = OPS_MD.parent
    for pat in FIELD_DOC_PATTERNS:
        for md in ref_dir.glob(pat):
            text = md.read_text(encoding="utf-8", errors="ignore")
            known |= {m.group(1).lower() for m in re.finditer(r"`([a-z][a-z0-9_]{2,40})`", text)}
    return known


def unknown_field_tokens(formula: str, known: set[str]) -> list[str]:
    tree = ast.parse(formula, mode="eval")
    called = {getattr(n.func, "id", "").lower() for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    bare = {n.id.lower() for n in ast.walk(tree) if isinstance(n, ast.Name)}
    bare -= called
    bad = []
    for name in sorted(bare):
        if name in known or name.isdigit():
            continue
        if re.match(r"^alpha191_\d{3}$", name):   # 平台已注册的 191 因子名
            continue
        if re.match(r"^(bs|is|cf|cal|val|fin|gro|op|ma|osc|vi|barra)_", name):
            continue
        bad.append(name)
    return bad


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


def analyze(name: str, formula: str, platform_ops: set[str], known_fields: set[str] | None = None) -> dict:
    tree = ast.parse(formula, mode="eval")
    called = {getattr(n.func, "id", "").lower() for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    local_ops = sorted(fn for fn in called if fn in LOCAL_TS_ALIASES and fn not in platform_ops)
    unknown_ops = sorted(fn for fn in called if fn not in platform_ops)
    unknown_fields = unknown_field_tokens(formula, known_fields) if known_fields is not None else []
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
                needs_scale=needs_scale, cost=cost, n_ops=len(called), local_ops=local_ops,
                unknown_ops=unknown_ops, unknown_fields=unknown_fields)


PY_OP_ALLOW = {
    "Factor", "RANK", "ZSCORE", "DELAY", "SUM", "MA", "STD", "STDDEV", "TS_MAX",
    "TS_MAX", "CORR", "ABS", "RETURNS", "np", "numpy",
}


def _code_only(src: str) -> str:
    """去掉注释与字符串字面量，只留代码 token（避免把文档里描述的坏模式误报）。"""
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except Exception:
        return src
    return " ".join(t.string for t in toks
                    if t.type not in (tokenize.COMMENT, tokenize.STRING))


def python_candidate_check(py_path: Path) -> dict:
    """Python 合成因子候选（`name ~ file.py ~ dir`）的提交前检查：存在性 + 语法 + 未定义名。"""
    if not py_path.exists():
        return dict(ok=False, notes=[f"Python 文件不存在: {py_path}"])
    source = py_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return dict(ok=False, notes=[f"Python 语法错误: {exc}"])
    defined = set(dir(builtins))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            defined.add(node.id)
        elif isinstance(node, ast.arg):
            defined.add(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            defined.add(node.name)
    loads = {n.id for n in ast.walk(tree)
             if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    unknown = sorted(n for n in loads if n not in defined and n not in PY_OP_ALLOW)
    notes = []
    if unknown:
        notes.append("未定义名（平台会 NameError）: " + "|".join(unknown))
    # --- 2026-09-29 增补：未来泄漏静态模式（pythonindex1 教训）-------------------
    # 平台 Python 索引固定 [date, symbol]（level 0 = 日期）。历史事故：
    # `str(v)[:4].isdigit()` 兜底把 "000001.SZ" 误判为日期层 → 按股票全样本 z-score
    # （均值/标准差/分位用整段回测窗口，含未来）→ 平台净超额 20.3% 虚高到 46.7%。
    code = _code_only(source)
    leak = []
    if re.search(r"isdigit\(\s*\)", code) and "get_level_values" in code:
        leak.append("用取值格式探测索引层（str(...).isdigit）——会把 symbol 误判为日期层")
    if re.search(r"groupby\(\s*level\s*=\s*1\s*\)", code) or \
       re.search(r"groupby\(\s*(level\s*=\s*)?[\"']symbol[\"']\s*\)", code):
        leak.append("按 level=1/symbol 层 groupby——平台 [date, symbol] 下非 0 层是股票，"
                    "全样本 mean/std/quantile 即未来泄漏")
    if leak:
        notes.append("⚠ 泄漏风险: " + "；".join(leak)
                     + " → 改为逐日截面 groupby(level=0)，并跑 scripts/repaint_check.py")
    return dict(ok=not unknown and not leak, notes=notes)


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__); return 2
    path = Path(args[0])
    ops = load_platform_ops()
    known_fields = load_known_fields()
    board_names: set[str] = set()
    board_norm: dict[str, set[str]] = {}
    try:
        from board_name_guard import load_board_names, normalize
        board_names = load_board_names()
        for b in board_names:
            board_norm.setdefault(normalize(b), set()).add(b)
    except Exception as exc:  # 榜单文件缺失不应阻塞提交前预检
        print(f"（榜单撞名检查跳过：{exc}）")
    print(f"候选文件: {path}")
    print(f"平台算子名: {len(ops)}；已知字段名: {len(known_fields)}；榜单席位名: {len(board_names)}\n")
    rows = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"): continue
        parts = [p.strip() for p in line.split("~")]
        name, formula = parts[0], parts[1]
        direction = parts[2] if len(parts) > 2 else "?"
        if formula.lower().endswith(".py"):
            py = Path(formula)
            if not py.is_absolute():
                py = path.parent / py
            rows.append({"name": name, "formula": formula, "kind": "python",
                         "direction": direction, **python_candidate_check(py)})
            continue
        rows.append(analyze(name, formula, ops, known_fields) | {"direction": direction})
    print(f"{'cand':30s} {'撞名':>6s} {'脆弱':>6s} {'估计量级':>10s} {'建议k':>6s} {'费用':>5s}  备注")
    for r in rows:
        if r.get("kind") == "python":
            print(f"{r['name']:30s} python合成  {'OK' if r['ok'] else 'FAIL'}  {'; '.join(r['notes'])}"
                  f"  （费用按平台运行时长计档；池合成实测约 6.0/条）")
            for hit in board_collision(r["name"], board_names, board_norm):
                print(f"     ⚠ 榜单撞名: {hit} → 先改名再提交")
            continue
        note = []
        if r["needs_scale"]:
            note.append(f"需前置 POWER(10,{r['k']})")
        if r["fragile"]:
            note.append("方向必须实测")
        if r["local_ops"]:
            note.append("算子名不在平台表: " + "|".join(r["local_ops"]))
        if r["unknown_ops"]:
            note.append("算子名不在平台表: " + "|".join(r["unknown_ops"]))
        if r["unknown_fields"]:
            note.append("字段不在平台字段表: " + "|".join(r["unknown_fields"]))
        print(f"{r['name']:30s} {('有' if r['collisions'] else '无'):>6s} "
              f"{('有' if r['fragile'] else '无'):>6s} {r['est']:>10.3g} {r['k']:>6d} {r['cost']:>5.1f}  {'; '.join(note)}")
        if r["collisions"]:
            print(f"     ⚠ 裸字段与平台算子撞名: {r['collisions']} → 改用算子形式或换字段")
        if r["fragile"]:
            print(f"     ⚠ 分母含相关系数/有符号近零字段（{','.join(r['fragile'])}）→ 平台排序/方向不可预测，优先替换、方向必须实测")
        if r["local_ops"]:
            sugg = "; ".join(f"{o}→{LOCAL_TS_ALIASES[o]}" for o in r["local_ops"])
            print(f"     ⚠ 本地算子名不在平台算子表（{sugg}）→ 直接提交会 run failed，先换名")
        if r["unknown_ops"]:
            print(f"     ⚠ 算子名不在平台算子表: {r['unknown_ops']} → 直接提交会 run failed（变量未定义）")
        if r["unknown_fields"]:
            print(f"     ⚠ 字段不在平台字段表: {r['unknown_fields']} → Missing required base factors，先换字段/表达式")
        for hit in board_collision(r["name"], board_names, board_norm):
            print(f"     ⚠ 榜单撞名: {hit} → 先改名再提交")
    total = sum(r.get("cost", 0.0) for r in rows)
    print(f"\n预估费用: {total:.1f} 算力（{len(rows)} 条）")
    # 历史同式检查（2026-10-09 新增）：与仓库内已提交过的候选做腿集去重
    # 起因：POOL6-CAND-C-20261009 与 LAMD10-K5V2-20260929 同式（写法不同）未被发现。
    try:
        import dup_formula_check as DFC
        hist: dict[str, list[dict]] = {}
        for fpath in DFC.iter_candidate_files([]):
            for hrow in DFC.parse_candidates(fpath):
                hist.setdefault(DFC.canonical(hrow["formula"]), []).append(hrow)
        flagged = 0
        for r in rows:
            if r.get("kind") == "python":
                continue
            hits = [h for h in hist.get(DFC.canonical(r["formula"]), []) if h["name"] != r["name"]]
            if hits:
                flagged += 1
                shown = ", ".join(f"{h['name']}@{h['file']}:{h['line']}" for h in hits[:3])
                print(f"     ⚠ 历史同式: {r['name']} ≈ {shown} → 已测过，换候选或说明复测目的")
        if flagged:
            print(f"⚠ {flagged} 条候选与历史已提交公式同式（详见 scripts/dup_formula_check.py）")
    except Exception as exc:  # noqa: BLE001 去重检查失败不应阻塞预检
        print(f"（历史同式检查跳过：{exc}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
