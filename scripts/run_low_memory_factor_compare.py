#!/usr/bin/env python3
"""Run local factor comparisons through guarded, serial worker processes.

The factor evaluator keeps a large full-A panel in memory.  A fresh worker per
handler prevents pandas allocator growth from accumulating across dozens of
handlers, while the parent watches both worker RSS and system availability.
Completed worker JSON files are durable and can be reused after an interruption.
This script is offline only; it never contacts PandaAI or Tushare.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import psutil


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
GB = 1024**3


def _json_default(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return value


def _worker_result_path(root: Path, mode: str) -> Path:
    if mode == "full":
        return root / "all_factor_local_compare.json"
    return root / "positive_factor_recent_local_compare.json"


def _records_by_handler(records: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        handler = record.get("handler")
        if handler:
            grouped[str(handler)].append(record)
    return dict(sorted(grouped.items()))


def _pack_handler_groups(
    grouped: dict[str, list[dict[str, Any]]], pack_size: int
) -> list[tuple[str, list[dict[str, Any]]]]:
    handlers = list(grouped.items())
    tasks: list[tuple[str, list[dict[str, Any]]]] = []
    for offset in range(0, len(handlers), pack_size):
        chunk = handlers[offset : offset + pack_size]
        task_id = f"worker_{offset // pack_size + 1:03d}_{chunk[0][0]}"
        records = [record for _, handler_records in chunk for record in handler_records]
        tasks.append((task_id, records))
    return tasks


def _terminate_tree(process: subprocess.Popen[str]) -> None:
    try:
        parent = psutil.Process(process.pid)
        children = parent.children(recursive=True)
    except psutil.Error:
        children = []
    for child in reversed(children):
        try:
            child.terminate()
        except psutil.Error:
            pass
    try:
        process.terminate()
    except OSError:
        pass
    gone, alive = psutil.wait_procs(children, timeout=3)
    del gone
    for child in alive:
        try:
            child.kill()
        except psutil.Error:
            pass
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _tree_rss(process: subprocess.Popen[str]) -> int:
    try:
        root = psutil.Process(process.pid)
        return root.memory_info().rss + sum(
            child.memory_info().rss
            for child in root.children(recursive=True)
            if child.is_running()
        )
    except psutil.Error:
        return 0


def run_guarded(
    command: list[str],
    *,
    cwd: Path,
    max_rss: int,
    min_available: int,
    poll_seconds: float,
) -> int:
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONUNBUFFERED": "1",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
    )
    print("worker_command=" + " ".join(command), flush=True)
    process = subprocess.Popen(command, cwd=cwd, env=environment)
    try:
        try:
            psutil.Process(process.pid).nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        except (AttributeError, psutil.Error, OSError):
            pass
        last_report = 0.0
        while process.poll() is None:
            rss = _tree_rss(process)
            available = psutil.virtual_memory().available
            now = time.monotonic()
            if now - last_report >= 10.0:
                print(
                    f"worker_guard rss_gb={rss / GB:.2f} available_gb={available / GB:.2f}",
                    flush=True,
                )
                last_report = now
            if rss > max_rss:
                print(
                    f"worker_guard=terminate reason=rss_limit rss_gb={rss / GB:.2f} "
                    f"limit_gb={max_rss / GB:.2f}",
                    flush=True,
                )
                _terminate_tree(process)
                return 70
            if available < min_available:
                print(
                    f"worker_guard=terminate reason=available_memory available_gb={available / GB:.2f} "
                    f"minimum_gb={min_available / GB:.2f}",
                    flush=True,
                )
                _terminate_tree(process)
                return 71
            time.sleep(poll_seconds)
        return int(process.returncode or 0)
    except KeyboardInterrupt:
        print("worker_guard=terminate reason=keyboard_interrupt", flush=True)
        _terminate_tree(process)
        raise


def _load_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _worker_complete(path: Path, expected_ids: set[str]) -> bool:
    if not path.is_file():
        return False
    try:
        payload = _load_payload(path)
    except (OSError, json.JSONDecodeError):
        return False
    actual_ids = {
        str(row.get("id"))
        for row in payload.get("results", []) + payload.get("unsupported", [])
        if row.get("id")
    }
    return actual_ids == expected_ids


def _parse_ids(records: list[dict[str, Any]]) -> list[str]:
    return [str(record["id"]) for record in records]


def _full_worker_command(args: argparse.Namespace, record_ids: list[str], output: Path) -> list[str]:
    command = [
        sys.executable,
        str(PROJECT_ROOT / "scripts/positive_factor_local_compare.py"),
        "--universe",
        "full_a",
        "--price-root",
        str(args.price_root),
        "--cap-root",
        str(args.cap_root),
        "--financial-root",
        str(args.financial_root),
        "--output",
        str(output),
        "--platform-net-filter",
        "all",
        "--data-start",
        "20180101",
        "--market-cap-field",
        "total_mv",
        "--label-offset",
        "1",
    ]
    for record_id in record_ids:
        command.extend(["--id", record_id])
    return command


def _recent_worker_command(args: argparse.Namespace, record_ids: list[str], output: Path) -> list[str]:
    command = [
        sys.executable,
        str(PROJECT_ROOT / "scripts/positive_factor_recent_local_compare.py"),
        "--recent-start",
        args.recent_start,
        "--price-root",
        str(args.price_root),
        "--cap-root",
        str(args.cap_root),
        "--financial-root",
        str(args.financial_root),
        "--output",
        str(output),
    ]
    for record_id in record_ids:
        command.extend(["--id", record_id])
    return command


def _run_full(args: argparse.Namespace) -> int:
    sys.path.insert(0, str(SCRIPTS_ROOT))
    from positive_factor_local_compare import (  # noqa: PLC0415
        DATA_START,
        END,
        formula_catalog,
        saved_records,
        write_outputs,
    )

    supported, unsupported = saved_records(formula_catalog(), "all")
    if args.only_name:
        wanted = set(args.only_name)
        supported = [record for record in supported if record["name"] in wanted]
        unsupported = [record for record in unsupported if record.get("name") in wanted]
    if args.only_id:
        wanted = set(args.only_id)
        supported = [record for record in supported if record["id"] in wanted]
        unsupported = [record for record in unsupported if record.get("id") in wanted]
    grouped = _records_by_handler(supported)
    if not grouped:
        raise RuntimeError("No supported saved handlers found")
    output_root = Path(args.output)
    final_json = output_root / "all_factor_local_compare.json"
    if final_json.exists():
        raise RuntimeError(f"Refusing to overwrite completed output: {final_json}")
    if output_root.exists() and any(output_root.iterdir()):
        raise RuntimeError(f"Output directory is not empty: {output_root}")
    tasks = _pack_handler_groups(grouped, args.pack_handlers)

    worker_root = output_root.parent / f".{output_root.name}.workers"
    worker_root.mkdir(parents=True, exist_ok=True)
    state_path = output_root.parent / f".{output_root.name}.state.json"
    state: dict[str, Any] = {}
    if state_path.exists():
        state = _load_payload(state_path)

    result_rows: dict[str, dict[str, Any]] = {}
    result_unsupported: dict[str, dict[str, Any]] = {
        str(row["id"]): row for row in unsupported if row.get("id")
    }
    records_by_id = {str(record["id"]): record for record in supported}
    max_rss = int(args.max_child_rss_gb * GB)
    min_available = int(args.min_available_gb * GB)
    completed = 0
    for task_id, records in tasks:
        record_ids = _parse_ids(records)
        worker_dir = worker_root / task_id
        worker_path = _worker_result_path(worker_dir, "full")
        expected_ids = {str(record["id"]) for record in records}
        if _worker_complete(worker_path, expected_ids):
            payload = _load_payload(worker_path)
            completed += 1
            print(f"reuse_worker={task_id} records={len(records)}", flush=True)
        else:
            worker_dir.mkdir(parents=True, exist_ok=True)
            command = _full_worker_command(args, record_ids, worker_dir)
            return_code = run_guarded(
                command,
                cwd=PROJECT_ROOT,
                max_rss=max_rss,
                min_available=min_available,
                poll_seconds=args.poll_seconds,
            )
            if return_code != 0:
                raise RuntimeError(f"Worker failed for {task_id} with exit code {return_code}")
            if not _worker_complete(worker_path, expected_ids):
                raise RuntimeError(f"Worker output is incomplete for {task_id}: {worker_path}")
            payload = _load_payload(worker_path)
            completed += 1
        for row in payload.get("results", []):
            result_rows[str(row["id"])] = row
        for row in payload.get("unsupported", []):
            result_unsupported[str(row["id"])] = row
        state.update(
            {
                "mode": "full",
                "output": str(output_root),
                "alignment_rule_version": payload.get("settings", {}).get("alignment_rule_version"),
                "completed_tasks": completed,
                "total_tasks": len(tasks),
                "last_task": task_id,
            }
        )
        state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2, default=_json_default) + "\n",
            encoding="utf-8",
        )

    unresolved = sorted(set(records_by_id) - set(result_rows) - set(result_unsupported))
    if unresolved:
        raise RuntimeError(f"Missing worker results for {len(unresolved)} saved records")
    final_supported = [record for record in supported if str(record["id"]) in result_rows]
    final_unsupported = [
        row
        for row in list(result_unsupported.values())
        if str(row.get("id")) not in result_rows
    ]
    rows = sorted(result_rows.values(), key=lambda row: str(row.get("id")))
    sample_settings = _load_payload(
        _worker_result_path(worker_root / tasks[0][0], "full")
    ).get("settings", {})
    output_root.mkdir(parents=True, exist_ok=True)
    write_outputs(
        final_supported,
        final_unsupported,
        rows,
        output_root,
        "full_a",
        int(sample_settings.get("pool_count", 0)),
        DATA_START,
        1,
        "total_mv",
        "all",
        sample_settings.get("market_field_sources") or {},
    )
    print(f"completed_tasks={completed}/{len(tasks)}", flush=True)
    print(f"report={output_root / 'all_factor_local_compare.md'}", flush=True)
    return 0


def _run_recent(args: argparse.Namespace) -> int:
    sys.path.insert(0, str(SCRIPTS_ROOT))
    import positive_factor_recent_local_compare as recent  # noqa: PLC0415

    supported, unsupported = recent.saved_records(recent.formula_catalog(), "positive")
    if args.only_name:
        wanted = set(args.only_name)
        supported = [record for record in supported if record["name"] in wanted]
        unsupported = [record for record in unsupported if record.get("name") in wanted]
    if args.only_id:
        wanted = set(args.only_id)
        supported = [record for record in supported if record["id"] in wanted]
        unsupported = [record for record in unsupported if record.get("id") in wanted]
    grouped = _records_by_handler(supported)
    if not grouped:
        raise RuntimeError("No supported positive saved handlers found")
    output_root = Path(args.output)
    paths = recent.output_paths(output_root)
    if any(path.exists() for path in paths.values()):
        raise RuntimeError(f"Refusing to overwrite completed recent output: {output_root}")
    if output_root.exists() and any(output_root.iterdir()):
        raise RuntimeError(f"Output directory is not empty: {output_root}")
    tasks = _pack_handler_groups(grouped, args.pack_handlers)

    worker_root = output_root.parent / f".{output_root.name}.workers"
    worker_root.mkdir(parents=True, exist_ok=True)
    max_rss = int(args.max_child_rss_gb * GB)
    min_available = int(args.min_available_gb * GB)
    result_rows: dict[str, dict[str, Any]] = {}
    result_unsupported: dict[str, dict[str, Any]] = {
        str(row["id"]): row for row in unsupported if row.get("id")
    }
    completed = 0
    for task_id, records in tasks:
        record_ids = _parse_ids(records)
        worker_dir = worker_root / task_id
        worker_path = _worker_result_path(worker_dir, "recent")
        expected_ids = {str(record["id"]) for record in records}
        if _worker_complete(worker_path, expected_ids):
            payload = _load_payload(worker_path)
            completed += 1
            print(f"reuse_worker={task_id} records={len(records)}", flush=True)
        else:
            worker_dir.mkdir(parents=True, exist_ok=True)
            command = _recent_worker_command(args, record_ids, worker_dir)
            return_code = run_guarded(
                command,
                cwd=PROJECT_ROOT,
                max_rss=max_rss,
                min_available=min_available,
                poll_seconds=args.poll_seconds,
            )
            if return_code != 0:
                raise RuntimeError(f"Worker failed for {task_id} with exit code {return_code}")
            if not _worker_complete(worker_path, expected_ids):
                raise RuntimeError(f"Worker output is incomplete for {task_id}: {worker_path}")
            payload = _load_payload(worker_path)
            completed += 1
        for row in payload.get("results", []):
            result_rows[str(row["id"])] = row
        for row in payload.get("unsupported", []):
            result_unsupported[str(row["id"])] = row

    expected_ids = {str(record["id"]) for record in supported}
    unresolved = sorted(expected_ids - set(result_rows) - set(result_unsupported))
    if unresolved:
        raise RuntimeError(f"Missing recent worker results for {len(unresolved)} saved records")
    final_unsupported = [
        row
        for row in result_unsupported.values()
        if str(row.get("id")) not in result_rows
    ]
    rows = sorted(
        result_rows.values(),
        key=lambda row: (
            row.get("recent_net_excess_pct") is None,
            -(row.get("recent_net_excess_pct") or 0.0),
        ),
    )
    sample_settings = _load_payload(
        _worker_result_path(worker_root / tasks[0][0], "recent")
    ).get("settings", {})
    sample_settings.update(
        {
            "platform_positive_records": len(supported) + len(unsupported),
            "locally_reproduced_records": len(rows),
            "unsupported_records": len(final_unsupported),
        }
    )
    recent.write_outputs(paths, sample_settings, rows, final_unsupported)
    print(f"completed_tasks={completed}/{len(tasks)}", flush=True)
    print(f"report={paths['md']}", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["full", "recent"], required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--price-root", required=True, type=Path)
    parser.add_argument("--cap-root", required=True, type=Path)
    parser.add_argument("--financial-root", required=True, type=Path)
    parser.add_argument("--recent-start", default="20260101")
    parser.add_argument(
        "--only-name",
        action="append",
        default=[],
        help="Diagnostic filter; repeat to run only selected saved factor names.",
    )
    parser.add_argument(
        "--only-id",
        action="append",
        default=[],
        help="Diagnostic filter; repeat to run only selected saved record ids.",
    )
    parser.add_argument("--max-child-rss-gb", type=float, default=3.25)
    parser.add_argument("--min-available-gb", type=float, default=2.25)
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    parser.add_argument(
        "--pack-handlers",
        type=int,
        default=1,
        help="Number of handler groups per fresh worker; 1 is the safest setting.",
    )
    args = parser.parse_args()
    if args.max_child_rss_gb <= 0 or args.min_available_gb <= 0:
        raise SystemExit("memory limits must be positive")
    if args.pack_handlers <= 0:
        raise SystemExit("--pack-handlers must be positive")
    if args.mode == "full":
        return _run_full(args)
    return _run_recent(args)


if __name__ == "__main__":
    raise SystemExit(main())
