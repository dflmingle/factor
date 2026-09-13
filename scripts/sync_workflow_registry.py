#!/usr/bin/env python3
"""Synchronize PandaAI workflow metadata into a local audit registry.

This command is read-only with respect to PandaAI: it calls ``factor_list`` and
``factor_info`` only.  It does not create, update, run, or delete factors.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from platform_test_config_report import write_outputs as write_config_outputs

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_JSON = PROJECT_ROOT / "pandaai-workflow-registry.json"
REGISTRY_MD = PROJECT_ROOT / "pandaai-workflow-registry.md"

LOCAL_WORKFLOW_SUPPLEMENTS: dict[str, dict[str, Any]] = {
    "STFILTER-T10-SIZE-H03-T10-20260911": {
        "sources": ["current-stfilter-workflow.png", "corr-t10-size-vs-h03-20260911.md"],
        "note": "The platform list exposes two factor-analysis nodes while factor_info exposes only one content field. Node order is mapped from the saved canvas screenshot and the saved correlation report.",
        "nodes": [
            {
                "node_id": "388faa80-4f7c-40b9-b32c-5d475b91a855",
                "role": "T10-SIZE",
                "formula": "(RANK(1-RETURNS(CLOSE,40)) + RANK((SUM(VOLUME*(OPEN+CLOSE)/2,250)/SUM(VOLUME,250))/CLOSE-1) + RANK(1-MA(TURNOVER,21)/MA(TURNOVER,504)) + RANK(-ZSCORE(RANK(MARKET_CAP)))) / 4",
                "direction": "1",
                "mapping_confidence": "inferred from saved canvas node order",
            },
            {
                "node_id": "5618284d-a13a-41f9-a48a-cf88e7e42632",
                "role": "H03-T10-SINGLE",
                "formula": "RANK(SUM((HIGH-LOW)/(DELAY(CLOSE,1)+0.000001),60)/(SUM(AMOUNT,60)+1))",
                "direction": "1",
                "mapping_confidence": "inferred from saved canvas node order and factor_info",
            },
        ],
    },
    "CORR-20260911-T10-SIZE-H03-T10": {
        "sources": ["corr-t10-size-vs-h03-20260911.md"],
        "note": "The correlation workflow has no feature_tag factor nodes in factor_list; inputs are recorded from the saved correlation report.",
        "inputs": [
            {
                "role": "T10-SIZE",
                "formula": "(RANK(1-RETURNS(CLOSE,40)) + RANK((SUM(VOLUME*(OPEN+CLOSE)/2,250)/SUM(VOLUME,250))/CLOSE-1) + RANK(1-MA(TURNOVER,21)/MA(TURNOVER,504)) + RANK(-ZSCORE(RANK(MARKET_CAP)))) / 4",
            },
            {
                "role": "H03-T10-SINGLE",
                "formula": "RANK(SUM((HIGH-LOW)/(DELAY(CLOSE,1)+0.000001),60)/(SUM(AMOUNT,60)+1))",
            },
        ],
    },
}


def cli_json(args: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        ["pandaai-cli", "--json", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"pandaai-cli {' '.join(args)} failed: {detail}")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"pandaai-cli {' '.join(args)} returned invalid JSON: {completed.stdout[:500]}"
        ) from exc


def list_platform_factors() -> list[dict[str, Any]]:
    first = cli_json(["factor_list", "--limit", "100", "--page", "1", "--no-detail"])
    factors = list(first.get("factors", []))
    total = int(first.get("total", len(factors)))
    page = 2
    while len(factors) < total:
        response = cli_json(["factor_list", "--limit", "100", "--page", str(page), "--no-detail"])
        page_factors = response.get("factors", [])
        if not page_factors:
            break
        factors.extend(page_factors)
        page += 1
    unique: dict[str, dict[str, Any]] = {}
    for factor in factors:
        factor_id = factor.get("_id")
        if factor_id:
            unique[factor_id] = factor
    return list(unique.values())


def load_local_states() -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    entries: list[dict[str, Any]] = []
    by_factor: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in sorted(PROJECT_ROOT.glob("*.txt.state.json")):
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            entries.append({"state_file": path.name, "error": str(exc)})
            continue
        if not isinstance(state, dict):
            continue
        for candidate_name, record in state.items():
            if not isinstance(record, dict):
                continue
            row = {
                "state_file": path.name,
                "candidate_name": candidate_name,
                "factor_id": record.get("factor_id"),
                "run_id": record.get("run_id"),
                "raw_result": record.get("raw_result"),
                "metrics": record.get("metrics", {}),
            }
            entries.append(row)
            if row["factor_id"]:
                by_factor[row["factor_id"]].append(row)
    return entries, by_factor


def load_manifest_metadata() -> dict[str, dict[str, str]]:
    metadata: dict[str, dict[str, str]] = {}
    for path in sorted(PROJECT_ROOT.glob("*.txt")):
        if path.name.endswith(".state.json"):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            if not line.strip() or line.lstrip().startswith("#") or line.count("~") < 2:
                continue
            pieces = [piece.strip() for piece in line.split("~")]
            if len(pieces) < 3:
                continue
            name, direction = pieces[0], pieces[-1]
            if direction not in {"0", "1"}:
                continue
            formula = " ~ ".join(pieces[1:-1])
            metadata.setdefault(
                name,
                {"manifest": path.name, "formula": formula, "direction": direction},
            )
    return metadata


def factor_info(factor_id: str) -> dict[str, Any]:
    response = cli_json(["factor_info", factor_id])
    fields = (
        "_id", "name", "last_run_id", "mode", "content", "start_date", "end_date",
        "market", "adjustment_cycle", "group_number", "factor_direction", "stock_pool",
    )
    result = {field: response.get(field) for field in fields if field in response}
    content = result.pop("content", None)
    if result.get("mode") == "formula":
        result["content"] = content
    elif content is not None:
        encoded = str(content).encode("utf-8")
        result["content_sha256"] = hashlib.sha256(encoded).hexdigest()
        result["content_length"] = len(str(content))
    return result


def compact_platform(factor: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "_id", "name", "description", "owner", "create_at", "update_at", "create_source",
        "last_run_id", "category", "display_tag", "chat_status", "publish_status",
        "checkpoint_content_hash",
    )
    row = {field: factor.get(field) for field in fields if field in factor}
    row["nodes"] = (factor.get("feature_tag") or {}).get("factor", [])
    return row


def markdown_escape(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def build_markdown(registry: dict[str, Any]) -> str:
    summary = registry["summary"]
    lines = [
        "# PandaAI Workflow Registry",
        "",
        f"同步时间：`{registry['synced_at']}`。本文件由只读 `factor_list`/`factor_info` 查询生成，未创建、修改、运行或删除工作流。",
        "",
        "## 盘点",
        "",
        f"平台当前工作流：**{summary['platform_workflows']}**；本地状态条目：**{summary['local_state_entries']}**；按 `factor_id` 匹配：**{summary['matched_workflows']}**。",
        f"当前平台对象但本地没有状态记录：**{summary['current_without_local_record']}**；本地记录但平台已不存在：**{summary['local_archived_records']}**。",
        "",
        "`node_title` 是平台接口返回的画布节点标题。当前大多数 CLI 工作流的标题都是 `因子分析`；工作流显示名和 `_id` 才是定位对象的主键。",
        "",
        "## 本地补充映射",
        "",
        "平台 `factor_info` 对多节点工作流只返回单个 `content` 时，以下内容来自项目内保存的画布截图/分析报告，并标注了推断依据。",
        "",
    ]
    supplements = [row for row in registry["workflows"] if row.get("local_supplement")]
    for row in supplements:
        supplement = row["local_supplement"]
        lines.append(f"### {markdown_escape(row.get('name'))}")
        lines.append("")
        lines.append(
            f"来源：{markdown_escape(', '.join(supplement.get('sources', [])))}。"
            f"{markdown_escape(supplement.get('note', ''))}"
        )
        lines.append("")
        items = supplement.get("nodes", supplement.get("inputs", []))
        lines.append("| 角色 | node_id | 公式 | 映射说明 |")
        lines.append("|---|---|---|---|")
        for item in items:
            lines.append(
                "| " + " | ".join(
                    markdown_escape(value)
                    for value in (
                        item.get("role"), item.get("node_id", ""), item.get("formula", ""),
                        item.get("mapping_confidence", "平台接口未返回节点 ID"),
                    )
                ) + " |"
            )
        lines.append("")
    if not supplements:
        lines.append("暂无。")
    lines.extend([
        "",
        "## 当前平台对象但本地缺记录",
        "",
        "| 工作流名 | workflow_id | 最近 run_id | 来源 | 节点 | 公式/内容 |",
    ])
    lines.append("|---|---|---|---|---|---|")
    for row in registry["current_without_local_record"]:
        info = row.get("factor_info", {})
        nodes = ", ".join(
            f"{node.get('node_title', '')} ({node.get('node_id', '')})"
            for node in row.get("nodes", [])
        ) or "接口未返回"
        lines.append(
            "| " + " | ".join(
                markdown_escape(value)
                for value in (
                    row.get("name"), row.get("_id"), row.get("last_run_id"),
                    row.get("create_source"), nodes, info.get("content", ""),
                )
            ) + " |"
        )
    if not registry["current_without_local_record"]:
        lines.append("| 无 | | | | | |")
    lines.extend([
        "",
        "## 本地记录但平台已不存在",
        "",
        "| 本地候选名 | factor_id | run_id | 状态文件 |",
        "|---|---|---|---|",
    ])
    for row in registry["local_archived_records"]:
        lines.append(
            "| " + " | ".join(
                markdown_escape(row.get(key))
                for key in ("candidate_name", "factor_id", "run_id", "state_file")
            ) + " |"
        )
    if not registry["local_archived_records"]:
        lines.append("| 无 | | | |")
    lines.extend([
        "",
        "## 全量当前平台索引",
        "",
        "| 工作流名 | workflow_id | 最近 run_id | 本地登记 | 节点 ID/标题 | 平台公式/参数状态 |",
        "|---|---|---|---|---|---|",
    ])
    for row in registry["workflows"]:
        nodes = ", ".join(
            f"{node.get('node_id', '')} / {node.get('node_title', '')}"
            for node in row.get("nodes", [])
        ) or "无 feature_tag"
        info = row.get("factor_info", {})
        info_state = "已取得" if info.get("content") is not None or info.get("stock_pool") is not None else "未取得"
        lines.append(
            "| " + " | ".join(
                markdown_escape(value)
                for value in (
                    row.get("name"), row.get("_id"), row.get("last_run_id"),
                    "是" if row.get("local", {}).get("recorded") else "否",
                    nodes, info_state,
                )
            ) + " |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync PandaAI workflow metadata into a local registry")
    parser.add_argument("--no-info", action="store_true", help="skip per-workflow factor_info calls")
    args = parser.parse_args()

    try:
        platform = list_platform_factors()
        local_entries, local_by_factor = load_local_states()
        manifests = load_manifest_metadata()
        info_failures: dict[str, str] = {}
        workflows: list[dict[str, Any]] = []
        platform_ids = {factor.get("_id") for factor in platform}

        for factor in platform:
            factor_id = factor.get("_id")
            local_rows = local_by_factor.get(factor_id, [])
            info: dict[str, Any] = {}
            if not args.no_info and factor_id:
                try:
                    info = factor_info(factor_id)
                except RuntimeError as exc:
                    info_failures[factor_id] = str(exc)
            local_rows_with_manifest = []
            for local in local_rows:
                enriched = dict(local)
                manifest = manifests.get(local.get("candidate_name", ""))
                if manifest:
                    enriched["manifest_metadata"] = manifest
                local_rows_with_manifest.append(enriched)
            row = compact_platform(factor)
            row["factor_info"] = info
            if row.get("name") in LOCAL_WORKFLOW_SUPPLEMENTS:
                row["local_supplement"] = LOCAL_WORKFLOW_SUPPLEMENTS[row["name"]]
            row["local"] = {
                "recorded": bool(local_rows),
                "entries": local_rows_with_manifest,
            }
            workflows.append(row)

        archived = [entry for entry in local_entries if entry.get("factor_id") not in platform_ids]
        current_without = [row for row in workflows if not row["local"]["recorded"]]
        node_shapes: dict[str, int] = defaultdict(int)
        for row in workflows:
            shape = tuple(
                (node.get("node_id"), node.get("node_title"))
                for node in row.get("nodes", [])
            )
            node_shapes[json.dumps(shape, ensure_ascii=False)] += 1

        registry = {
            "schema_version": 1,
            "synced_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "source": "pandaai-cli factor_list + factor_info",
            "summary": {
                "platform_workflows": len(workflows),
                "local_state_entries": len([entry for entry in local_entries if "error" not in entry]),
                "local_unique_factor_ids": len(local_by_factor),
                "matched_workflows": len(workflows) - len(current_without),
                "current_without_local_record": len(current_without),
                "local_archived_records": len(archived),
                "factor_info_failures": len(info_failures),
                "node_shapes": dict(node_shapes),
            },
            "info_failures": info_failures,
            "workflows": workflows,
            "current_without_local_record": current_without,
            "local_archived_records": archived,
        }
        REGISTRY_JSON.write_text(
            json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        REGISTRY_MD.write_text(build_markdown(registry), encoding="utf-8")
        write_config_outputs(registry)
        print(json.dumps(registry["summary"], ensure_ascii=False, indent=2))
        print(f"wrote {REGISTRY_JSON.name}")
        print(f"wrote {REGISTRY_MD.name}")
        print("wrote pandaai-platform-test-configs.json")
        print("wrote pandaai-platform-test-configs.md")
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"sync failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
