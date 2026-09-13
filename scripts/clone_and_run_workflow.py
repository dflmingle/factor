#!/usr/bin/env python3
"""Clone a PandaAI workflow, apply research parameters, and run it once."""

from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from pathlib import Path
from typing import Any

import requests
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = Path.home() / ".pandaai" / "config.yaml"
DEFAULT_WORKFLOW_ID = "6aa40282ecb163ea7228d0d8"
DEFAULT_NAME = (
    "20\u65e5\u91cf\u4ef7\u7a81\u7834\u590d\u5408\u56e0\u5b50-\u514b\u9686-"
    "5Y-T10-G10-20260912"
)


def load_auth() -> tuple[str, str, str]:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    token = str(config.get("token", ""))
    uid = str(config.get("uid", ""))
    gateway = str(config.get("gateway_url", "https://www.pandaaiquant.com/pandaApi")).rstrip("/")
    if not token or not uid:
        raise RuntimeError("PandaAI token or uid is missing from the local config")
    return gateway, token, uid


def headers(token: str, uid: str, quantflow: bool = False) -> dict[str, str]:
    result = {"Authorization": token, "uid": uid, "Content-Type": "application/json"}
    if quantflow:
        result["quantflow-auth"] = "2"
    return result


def request_json(
    method: str,
    url: str,
    *,
    request_headers: dict[str, str],
    **kwargs: Any,
) -> tuple[requests.Response, Any]:
    response = requests.request(method, url, headers=request_headers, timeout=30, **kwargs)
    try:
        body = response.json()
    except ValueError:
        body = response.text[:1000]
    return response, body


def get_workflow(gateway: str, token: str, uid: str, workflow_id: str) -> dict[str, Any]:
    response, body = request_json(
        "GET",
        f"{gateway}/quantflow/api/workflow/query",
        request_headers=headers(token, uid),
        params={"workflow_id": workflow_id},
    )
    if response.status_code >= 400 or not isinstance(body, dict) or not body.get("nodes"):
        raise RuntimeError(f"workflow query failed: HTTP {response.status_code}: {body}")
    return body


def set_litegraph_properties(workflow: dict[str, Any], work_node: dict[str, Any], fields: dict[str, Any]) -> None:
    node_uuid = work_node.get("uuid")
    litegraph = workflow.get("litegraph", {})
    litegraph_node = next(
        (
            node
            for node in litegraph.get("nodes", [])
            if (node.get("flags") or {}).get("uuid") == node_uuid
        ),
        None,
    )
    if litegraph_node is None:
        raise RuntimeError(f"litegraph node is missing for {node_uuid}")

    properties = litegraph_node.setdefault("properties", {})
    input_names = {
        item.get("fieldName"): item.get("name")
        for item in litegraph_node.get("inputs", [])
        if item.get("fieldName") and item.get("name")
    }
    for field, value in fields.items():
        property_name = input_names.get(field)
        if property_name:
            properties[property_name] = value


def apply_parameters(
    workflow: dict[str, Any],
    *,
    name: str,
    start_date: str,
    end_date: str,
    cycle: str,
    groups: str,
    direction: str,
) -> dict[str, Any]:
    cloned = copy.deepcopy(workflow)
    cloned["name"] = name

    # Keep the graph, but remove server-owned fields so /save creates a clone.
    for key in (
        "_id",
        "owner",
        "create_at",
        "update_at",
        "feature_tag",
        "last_run_id",
        "publish_status",
        "subscription_id",
    ):
        cloned.pop(key, None)
    cloned["create_source"] = "cli"

    build_count = 0
    analysis_count = 0
    for node in cloned.get("nodes", []):
        node_type = node.get("name")
        if node_type == "FactorBuildProControl":
            fields = {"start_date": start_date, "end_date": end_date}
            node.setdefault("static_input_data", {}).update(fields)
            set_litegraph_properties(cloned, node, fields)
            build_count += 1
        elif node_type == "FactorAnalysisControl":
            fields = {
                "adjustment_cycle": cycle,
                "group_number": groups,
                "factor_direction": direction,
            }
            node.setdefault("static_input_data", {}).update(fields)
            set_litegraph_properties(cloned, node, fields)
            analysis_count += 1

    if build_count != 3 or analysis_count != 1:
        raise RuntimeError(f"unexpected graph shape: builds={build_count}, analyses={analysis_count}")
    return cloned


def create_clone(gateway: str, token: str, uid: str, workflow: dict[str, Any]) -> str:
    response, body = request_json(
        "POST",
        f"{gateway}/quantflow/api/workflow/save",
        request_headers=headers(token, uid),
        json=workflow,
    )
    if response.status_code >= 400 or not isinstance(body, dict) or body.get("code") != 0:
        raise RuntimeError(f"workflow clone failed: HTTP {response.status_code}: {body}")
    workflow_id = (body.get("data") or {}).get("workflow_id")
    if not workflow_id:
        raise RuntimeError(f"workflow clone response has no workflow_id: {body}")
    return str(workflow_id)


def start_run(gateway: str, token: str, uid: str, workflow_id: str) -> str:
    # These are the resource values used by the web workflow editor. The CLI-sized
    # request is a fallback when the web scheduler has no matching server record.
    resource_sets = ((2, 4, 2), (4, 8, 4))
    for index, (cpu, memory, gpu) in enumerate(resource_sets):
        body = {
            "workflow_id": workflow_id,
            "server_cpu": cpu,
            "server_memory": memory,
            "server_gpu": gpu,
        }
        response, payload = request_json(
            "POST",
            f"{gateway}/quantflow/api/workflow/run_with_store",
            request_headers=headers(token, uid, quantflow=True),
            json=body,
        )
        if response.status_code < 400 and isinstance(payload, dict):
            run_id = (payload.get("data") or {}).get("workflow_run_id")
            if run_id:
                return str(run_id)
            raise RuntimeError(f"workflow run start response has no run id: {payload}")
        if response.status_code == 503 and index == 0:
            print("web resource scheduling unavailable; retrying with CLI resources", flush=True)
            continue
        raise RuntimeError(f"workflow run start failed: HTTP {response.status_code}: {payload}")
    raise RuntimeError("workflow run start failed for all resource configurations")


def wait_for_run(gateway: str, token: str, uid: str, run_id: str, timeout: int) -> dict[str, Any]:
    url = f"{gateway}/quantflow/api/workflow/run"
    started = time.monotonic()
    last_status: Any = None
    while time.monotonic() - started <= timeout:
        response, payload = request_json(
            "GET",
            url,
            request_headers=headers(token, uid),
            params={"workflow_run_id": run_id},
        )
        if response.status_code < 400 and isinstance(payload, dict) and payload.get("code") == 0:
            data = payload.get("data") or {}
            status = data.get("status")
            if status != last_status:
                print(f"run_status={status}", flush=True)
                last_status = status
            if status in (2, 3, 6):
                return data
        time.sleep(5)
    raise TimeoutError(f"workflow run timed out after {timeout} seconds")


def get_balance(gateway: str, token: str, uid: str) -> Any:
    response, payload = request_json(
        "GET",
        f"{gateway}/userWallet/myWallet",
        request_headers=headers(token, uid),
    )
    if response.status_code >= 400 or not isinstance(payload, dict):
        return None
    return payload.get("data")


def get_run_results(gateway: str, token: str, uid: str, workflow_id: str, run_id: str) -> dict[str, Any]:
    response, payload = request_json(
        "GET",
        f"{gateway}/quantflow/api/workflow/run",
        request_headers=headers(token, uid),
        params={"workflow_run_id": run_id},
    )
    if response.status_code >= 400 or not isinstance(payload, dict) or payload.get("code") != 0:
        raise RuntimeError(f"run detail query failed: HTTP {response.status_code}: {payload}")
    detail = payload.get("data") or {}
    result: dict[str, Any] = {
        "status": detail.get("status"),
        "duration_seconds": detail.get("duration_seconds"),
        "start_time": detail.get("start_time"),
        "end_time": detail.get("end_time"),
        "nodes": {},
        "factor_analysis": None,
    }
    for node_uuid, output_obj_id in (detail.get("output_data_obj") or {}).items():
        response, node_payload = request_json(
            "GET",
            f"{gateway}/quantflow/api/workflow/run/output",
            request_headers=headers(token, uid),
            params={"output_obj_id": output_obj_id},
        )
        if response.status_code < 400 and isinstance(node_payload, dict) and node_payload.get("code") == 0:
            result["nodes"][node_uuid] = node_payload.get("data")

    analysis_node_uuid = next(
        (
            node.get("uuid")
            for node in get_workflow(gateway, token, uid, workflow_id).get("nodes", [])
            if node.get("name") == "FactorAnalysisControl"
        ),
        None,
    )
    task_id = None
    if analysis_node_uuid:
        node_data = result["nodes"].get(analysis_node_uuid) or {}
        task_id = node_data.get("task_id")

    if task_id:
        factor_endpoints = [
            "query_factor_analysis_data",
            "query_one_group_data",
            "query_group_return_analysis",
            "query_last_date_top_factor",
            "query_return_chart",
            "query_ic_decay_chart",
            "query_ic_density_chart",
            "query_ic_sequence_chart",
            "query_ic_self_correlation_chart",
            "query_rank_ic_decay_chart",
            "query_rank_ic_density_chart",
            "query_rank_ic_sequence_chart",
            "query_rank_ic_self_correlation_chart",
            "query_factor_excess_chart",
        ]
        analysis: dict[str, Any] = {"task_id": task_id}
        for endpoint in factor_endpoints:
            response, payload = request_json(
                "GET",
                f"{gateway}/quantflow/api/factor/{endpoint}",
                request_headers=headers(token, uid),
                params={"task_id": task_id},
            )
            if response.status_code < 400 and isinstance(payload, dict) and payload.get("code") in (0, "200", 200):
                analysis[endpoint] = payload.get("data")
        result["factor_analysis"] = analysis
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow-id", default=DEFAULT_WORKFLOW_ID)
    parser.add_argument("--name", default=DEFAULT_NAME)
    parser.add_argument("--start", default="20210907")
    parser.add_argument("--end", default="20260907")
    parser.add_argument("--cycle", default="10")
    parser.add_argument("--groups", default="10")
    parser.add_argument("--direction", default="1")
    parser.add_argument("--timeout", type=int, default=1200)
    parser.add_argument("--output", default="workflow-6aa40282-composite-5y-t10-g10.result.json")
    args = parser.parse_args()

    gateway, token, uid = load_auth()
    balance_before = get_balance(gateway, token, uid)
    original = get_workflow(gateway, token, uid, args.workflow_id)
    clone = apply_parameters(
        original,
        name=args.name,
        start_date=args.start,
        end_date=args.end,
        cycle=args.cycle,
        groups=args.groups,
        direction=args.direction,
    )
    clone_id = create_clone(gateway, token, uid, clone)
    print(f"clone_workflow_id={clone_id}", flush=True)

    verified = get_workflow(gateway, token, uid, clone_id)
    run_id = start_run(gateway, token, uid, clone_id)
    print(f"workflow_run_id={run_id}", flush=True)
    run_detail = wait_for_run(gateway, token, uid, run_id, args.timeout)
    if run_detail.get("status") != 2:
        raise RuntimeError(f"workflow run did not succeed: {run_detail}")

    result = get_run_results(gateway, token, uid, clone_id, run_id)
    balance_after = get_balance(gateway, token, uid)
    output = {
        "source_workflow_id": args.workflow_id,
        "clone_workflow_id": clone_id,
        "workflow_run_id": run_id,
        "settings": {
            "start_date": args.start,
            "end_date": args.end,
            "adjustment_cycle": args.cycle,
            "group_number": args.groups,
            "factor_direction": args.direction,
            "stock_pool": "\u6caa\u6df1\u5168A",
        },
        "balance_before": balance_before,
        "balance_after": balance_after,
        "verified_workflow": {
            "name": verified.get("name"),
            "nodes": verified.get("nodes"),
        },
        "run": result,
    }
    path = PROJECT_ROOT / args.output
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"result_file={path}")
    print(json.dumps({"balance_before": balance_before, "balance_after": balance_after, "status": result.get("status")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
