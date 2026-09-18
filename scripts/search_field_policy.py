"""Shared field-boundary checks for local AlphaPROBE search adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from alignment_failure_registry import blocked_search_fields
from platform_alignment_rules import ALIGNMENT_RULE_VERSION, ALIGNMENT_VERIFIED_SEARCH_FIELDS


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FAILURE_REGISTRY = (
    PROJECT_ROOT / "research_reports" / "platform_alignment" / "factor_alignment_failure_registry.json"
)


def load_field_exclusion_policy(
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    """Load versioned field exclusions without making the registry mandatory."""
    path = Path(registry_path).expanduser() if registry_path else DEFAULT_FAILURE_REGISTRY
    if not path.exists():
        return {
            "path": str(path),
            "status": "missing",
            "blocked_fields": [],
            "blocked_field_reasons": {},
        }
    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    registry_version = payload.get("alignment_rule_version")
    if registry_version and registry_version != ALIGNMENT_RULE_VERSION:
        raise ValueError(
            f"Field failure registry uses alignment rule {registry_version!r}; "
            f"expected {ALIGNMENT_RULE_VERSION!r}"
        )
    field_risks = payload.get("field_risks") or []
    blocked = blocked_search_fields(payload)
    reasons = {
        str(item.get("field")): str(item.get("decision_reason") or "")
        for item in field_risks
        if item.get("decision") == "blocked"
    }
    return {
        "path": str(path),
        "status": "loaded",
        "alignment_rule_version": payload.get("alignment_rule_version"),
        "blocked_fields": sorted(blocked),
        "blocked_field_reasons": reasons,
    }


def parse_field_list(value: str | Path | None) -> list[str]:
    """Parse a comma- or newline-separated field list without data imports."""
    if value is None:
        return []
    raw_value = str(value)
    candidate = Path(raw_value).expanduser()
    try:
        is_file = candidate.is_file()
    except OSError:
        is_file = False
    raw_values = candidate.read_text(encoding="utf-8").splitlines() if is_file else [raw_value]
    fields: list[str] = []
    for raw_line in raw_values:
        line = raw_line.split("#", 1)[0].strip().lower()
        if not line:
            continue
        fields.extend(item for item in line.replace(",", " ").split() if item)
    return list(dict.fromkeys(fields))


def resolve_terminal_fields(
    *,
    active_fields: Iterable[str],
    mode: str,
    field_file: str | Path | None,
    price_volume_fields: Iterable[str],
    formula_fields: Iterable[str],
    allow_unverified_fields: bool,
    allow_blocked_fields: bool = False,
    failure_registry: str | Path | None = None,
) -> list[str]:
    """Resolve a GP terminal set and reject unverified broadening by default."""
    active = {str(field).strip().lower() for field in active_fields}
    if field_file is not None:
        requested_override = parse_field_list(field_file)
        if not requested_override:
            raise ValueError("--search-field-file does not contain any field names")
        requested = set(requested_override)
    elif mode == "price_volume":
        requested = {str(field).strip().lower() for field in price_volume_fields}
    elif mode == "verified":
        requested = set(ALIGNMENT_VERIFIED_SEARCH_FIELDS)
    elif mode == "base":
        requested = {str(field).strip().lower() for field in formula_fields}
    elif mode == "all":
        requested = active
    else:
        raise ValueError(f"Unsupported search field mode: {mode}")

    unverified = sorted(requested - set(ALIGNMENT_VERIFIED_SEARCH_FIELDS))
    if unverified and not allow_unverified_fields:
        preview = ", ".join(unverified[:12])
        suffix = "..." if len(unverified) > 12 else ""
        raise ValueError(
            "The requested search range contains unverified fields "
            f"({preview}{suffix}); use --allow-unverified-fields for diagnostic mode"
        )
    exclusion_policy = load_field_exclusion_policy(failure_registry)
    blocked = set(exclusion_policy["blocked_fields"])
    blocked_requested = sorted(requested.intersection(blocked))
    if blocked_requested and not allow_blocked_fields:
        requested -= blocked
    terminals = sorted(active.intersection(requested))
    if terminals:
        return terminals
    if blocked_requested and not allow_blocked_fields:
        raise ValueError(
            "The requested search range contains only fields blocked by the alignment failure registry "
            f"({', '.join(blocked_requested)}); use --allow-blocked-fields for diagnostic mode"
        )
    raise ValueError(
        "The requested search range has no locally available fields; "
        "check the Tushare cache or use an explicit valid field file"
    )


def resolve_named_search_fields(
    panel: Any,
    *,
    feature_set: str,
    extra_fields: str | Path | None,
    max_extra_fields: int,
    allow_unverified_fields: bool,
    base_feature_names: Iterable[str],
    fundamental_core_fields: Iterable[str],
    allow_blocked_fields: bool = False,
    failure_registry: str | Path | None = None,
) -> dict[str, Any]:
    """Resolve GFN named fields while preserving explicit diagnostic mode."""
    base_names = {str(field).strip().lower() for field in base_feature_names}
    exclusion_policy = load_field_exclusion_policy(failure_registry)
    blocked = set(exclusion_policy["blocked_fields"])
    requested_override = parse_field_list(extra_fields)
    if requested_override:
        requested = requested_override
        resolved_feature_set = "custom"
    elif feature_set == "price_volume":
        blocked_base_features = sorted(base_names.intersection(blocked))
        return {
            "feature_set": feature_set,
            "search_fields": [],
            "search_field_count": 0,
            "search_field_status": [],
            "unverified_fields": [],
            "allow_unverified_fields": allow_unverified_fields,
            "blocked_fields": blocked_base_features if not allow_blocked_fields else [],
            "allow_blocked_fields": allow_blocked_fields,
            "failure_registry": str(failure_registry or DEFAULT_FAILURE_REGISTRY),
        }
    elif feature_set == "verified":
        requested = sorted(ALIGNMENT_VERIFIED_SEARCH_FIELDS)
        resolved_feature_set = feature_set
    elif feature_set == "fundamental_core":
        requested = [str(field).strip().lower() for field in fundamental_core_fields]
        resolved_feature_set = feature_set
    elif feature_set == "all_active":
        active = set(panel.pandaai_field_store.active_search_fields(include_period_variants=True))
        requested = sorted(active - {str(field).strip().lower() for field in base_feature_names})
        resolved_feature_set = feature_set
    else:
        raise ValueError(f"Unsupported feature-set: {feature_set}")

    requested = [field for field in requested if field not in base_names]
    blocked_requested = sorted(set(requested).intersection(blocked))
    blocked_base_features = sorted(base_names.intersection(blocked))
    if blocked_requested and not allow_blocked_fields:
        requested = [field for field in requested if field not in blocked]
    if blocked_requested and not requested and not allow_blocked_fields:
        raise ValueError(
            "The requested GFN search range contains only fields blocked by the alignment failure registry "
            f"({', '.join(blocked_requested)}); use --allow-blocked-fields for diagnostic mode"
        )
    unverified = sorted(set(requested) - set(ALIGNMENT_VERIFIED_SEARCH_FIELDS))
    if unverified and not allow_unverified_fields:
        preview = ", ".join(unverified[:12])
        suffix = "..." if len(unverified) > 12 else ""
        raise ValueError(
            "The requested GFN search range contains unverified fields "
            f"({preview}{suffix}); use --allow-unverified-fields for diagnostic mode"
        )

    statuses = [panel.pandaai_field_store.status(field) for field in requested]
    unavailable = [
        str(item["field"])
        for item in statuses
        if item["status"] == "unavailable"
    ]
    if unavailable:
        details = [item for item in statuses if item["field"] in unavailable]
        detail_text = "; ".join(
            f"{item['field']}: {item.get('note') or item['status']}" for item in details
        )
        raise ValueError(
            "Requested named fields are unavailable in the local financial cache: "
            f"{detail_text}"
        )
    if max_extra_fields < 0:
        raise ValueError("--max-extra-fields must be non-negative; use 0 for no limit")
    if max_extra_fields and len(requested) > max_extra_fields:
        raise ValueError(
            f"Feature set {resolved_feature_set} resolves to {len(requested)} named fields, "
            f"above --max-extra-fields={max_extra_fields}; use a field file or --max-extra-fields 0"
        )
    return {
        "feature_set": resolved_feature_set,
        "search_fields": requested,
        "search_field_count": len(requested),
        "search_field_status": statuses,
        "unverified_fields": unverified,
        "allow_unverified_fields": allow_unverified_fields,
        "blocked_fields": (
            sorted(set(blocked_requested).union(blocked_base_features))
            if not allow_blocked_fields
            else []
        ),
        "allow_blocked_fields": allow_blocked_fields,
        "failure_registry": str(failure_registry or DEFAULT_FAILURE_REGISTRY),
    }
