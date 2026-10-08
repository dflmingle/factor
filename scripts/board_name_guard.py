"""提交前榜单撞名守卫：候选因子名不得与赛事榜单在用的席位名相同。

用法:
    python scripts/board_name_guard.py candidates.txt        # 候选文件（name ~ formula ~ ...）
    python scripts/board_name_guard.py --names A B C         # 直接给因子名
    python scripts/board_name_guard.py --self-test           # 现役席位应全清、通用名探针应命中

数据源:
    research_reports/platform_alignment/board-details-*/factors_all.csv（自动取最新目录）；
    可用 --board-csv 显式指定。匹配按原样 + 归一化（小写去非字母数字）双口径，
    因此 ``Foo-Bar_01`` 与 ``foobar01`` 也算撞名。

约束（2026-10-08 用户要求）：新因子的展示名只需与榜单全部在用名不同，
但不得照搬对手命名风格；本脚本只做“不同名”的机械校验，不生成命名建议。
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOARD_ROOT = ROOT / "research_reports" / "platform_alignment"

# 本队标识：榜单明细里属于我们自己的行要排除（现役席位本来就在榜上）
OUR_PARTICIPANT_ID = "70c703ce0eba4038bd8b4a9ebbc46ff6"
OUR_DISPLAY_NAME = "ddd"

# 现役 5 席（mingle 池，2026-10-08 快照）
LIVE_SEATS = [
    "t10-additions-20260911-T10-ADD-BM-20260911",
    "VERIFY10-E260910-04",
    "VERIFY10-F260910-12",
    "h03-t10-20260911-H03-T10-SINGLE",
    "size-only-20260911-SIZE-ONLY-20260911",
]
# 未入池通用名探针（与榜单重名的反面样张）
KNOWN_COLLIDING_PROBES = [
    "Alpha191因子_016",
    "Alpha191因子_042",
    "Alpha191因子_121",
    "Alpha101因子_040",
]


def normalize(name: str) -> str:
    """归一口径：小写 + 去掉一切非字母数字字符。"""
    return re.sub(r"[^0-9a-z]+", "", str(name).lower())


def latest_board_csv() -> Path:
    cands = sorted(BOARD_ROOT.glob("board-details-*/factors_all.csv"))
    if not cands:
        raise FileNotFoundError(f"未找到榜单明细 CSV：{BOARD_ROOT}/board-details-*/factors_all.csv")
    return cands[-1]


def load_board_names(board_csv: Path | None = None, exclude_ours: bool = True) -> set[str]:
    """榜单全部展示名（各池席位去重；默认剔除本队自己的行）。"""
    path = Path(board_csv) if board_csv else latest_board_csv()
    names: set[str] = set()
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            if exclude_ours and row.get("participant_id") == OUR_PARTICIPANT_ID:
                continue
            if exclude_ours and row.get("display_name") == OUR_DISPLAY_NAME:
                continue
            raw = (row.get("factor_name") or "").strip()
            if raw:
                names.add(raw)
    if not names:
        raise ValueError(f"榜单明细无 factor_name 列或全为空：{path}")
    return names


def check_names(names: list[str], board: set[str]) -> list[dict]:
    board_norm: dict[str, set[str]] = {}
    for b in board:
        board_norm.setdefault(normalize(b), set()).add(b)
    rows = []
    for name in names:
        exact = name in board
        fuzzy = sorted(board_norm.get(normalize(name), set()) - {name})
        rows.append({"name": name, "exact": exact, "fuzzy": fuzzy, "ok": not exact and not fuzzy})
    return rows


def parse_candidates(path: Path) -> list[str]:
    names = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        names.append(line.split("~")[0].strip())
    if not names:
        raise ValueError(f"候选文件没有有效行：{path}")
    return names


def self_test() -> int:
    board = load_board_names()
    live = check_names(LIVE_SEATS, board)
    probes = check_names(KNOWN_COLLIDING_PROBES, board)
    ok_live = all(r["ok"] for r in live)
    ok_probe = all(not r["ok"] for r in probes)
    print(f"榜单名 {len(board)} 个（{latest_board_csv().parent.name}）")
    print(f"现役 5 席全清: {ok_live}")
    print(f"通用名探针全命中: {ok_probe}")
    return 0 if (ok_live and ok_probe) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="榜单撞名守卫（提交前预检）")
    ap.add_argument("candidates", nargs="?", type=Path, help="候选文件（name ~ formula ~ direction）")
    ap.add_argument("--names", nargs="*", default=[], help="直接给定因子名")
    ap.add_argument("--board-csv", type=Path, default=None, help="显式指定榜单明细 CSV")
    ap.add_argument("--self-test", action="store_true", help="对现役席位与已知撞名探针做回归")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    names = list(args.names)
    if args.candidates:
        names += parse_candidates(args.candidates)
    if not names:
        ap.error("需要 candidates 文件或 --names")

    board = load_board_names(args.board_csv)
    rows = check_names(names, board)
    print(f"榜单名 {len(board)} 个（{latest_board_csv().parent.name}） 候选 {len(rows)} 条")
    print(f"{'候选名':40s} {'名单':>4s}  备注")
    for r in rows:
        if r["exact"]:
            note = "原样与榜单席位名相同 → 必须改名"
        elif r["fuzzy"]:
            note = "归一化后与榜单重名: " + "|".join(r["fuzzy"][:3])
        else:
            note = "榜单唯一"
        print(f"{r['name']:40s} {('撞' if not r['ok'] else '清'):>4s}  {note}")
    bad = [r["name"] for r in rows if not r["ok"]]
    if bad:
        print(f"\n✗ {len(bad)} 条与榜单重名，先改名再提交：{'、'.join(bad)}")
        return 1
    print("\n✓ 全部候选名与榜单不重名")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
