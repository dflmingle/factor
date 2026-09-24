"""换机交接自检：核对本机大体积本地缓存（*.pkl）是否齐全且与旧机一致。

只读、零平台算力。清单见
``research_reports/platform_alignment/handoff_20260924/local_data_manifest.json``。
缺失或不一致的条目会打印重建命令；全部通过时退出码为 0。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = (
    ROOT
    / "research_reports/platform_alignment/handoff_20260924/local_data_manifest.json"
)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def human(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f}{unit}"
        value /= 1024
    return f"{value:.1f}GB"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument(
        "--size-only",
        action="store_true",
        help="只比对文件大小，跳过 sha256（快速自检）",
    )
    args = parser.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    entries = manifest.get("entries", [])
    print(f"manifest: {args.manifest}")
    print(f"rule version: {manifest.get('rule_version', 'unknown')}")
    print(f"entries: {len(entries)}{' (size-only)' if args.size_only else ''}\n")

    failures: list[str] = []
    for entry in entries:
        path = ROOT / entry["path"]
        expected_size = int(entry.get("size_bytes", -1))
        expected_sha = entry.get("sha256")
        if not path.exists():
            print(f"MISSING  {entry['path']}")
            print(f"         rebuild: {entry.get('rebuild', 'n/a')}")
            failures.append(entry["path"])
            continue
        actual_size = path.stat().st_size
        if expected_size >= 0 and actual_size != expected_size:
            print(
                f"BAD SIZE {entry['path']} 本地 {human(actual_size)} != 清单 {human(expected_size)}"
            )
            print(f"         rebuild: {entry.get('rebuild', 'n/a')}")
            failures.append(entry["path"])
            continue
        if args.size_only or not expected_sha:
            print(f"OK       {entry['path']}  {human(actual_size)}")
            continue
        actual_sha = sha256_of(path)
        if actual_sha != expected_sha:
            print(f"BAD SHA  {entry['path']} 本地 {actual_sha[:16]} != 清单 {expected_sha[:16]}")
            print(f"         rebuild: {entry.get('rebuild', 'n/a')}")
            failures.append(entry["path"])
            continue
        print(f"OK       {entry['path']}  {human(actual_size)}  sha256={actual_sha[:16]}")

    print()
    if failures:
        print(f"{len(failures)}/{len(entries)} 项需要处理：先拷贝或重建，再重跑本脚本。")
        return 1
    print(f"全部 {len(entries)} 项与旧机一致。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
