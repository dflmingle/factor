#!/usr/bin/env python3
"""Resolve the local machine identity used in reproduction reports."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_CONFIG_PATH = PROJECT_ROOT / "machine_profile.local.json"
MACHINE_LABELS = {
    "home": "家用电脑",
    "office": "公司电脑",
}


def _read_local_config() -> dict[str, Any]:
    if not LOCAL_CONFIG_PATH.is_file():
        return {}
    try:
        value = json.loads(LOCAL_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Cannot read machine profile config {LOCAL_CONFIG_PATH}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"Machine profile config must be a JSON object: {LOCAL_CONFIG_PATH}")
    return value


def _normalise_profile(value: Any) -> str:
    profile = str(value or "").strip().lower()
    if profile not in MACHINE_LABELS:
        choices = ", ".join(sorted(MACHINE_LABELS))
        raise RuntimeError(
            f"Unknown machine profile {profile!r}; choose one of: {choices}"
        )
    return profile


def label_for_profile(profile: str) -> str:
    return MACHINE_LABELS[_normalise_profile(profile)]


def resolve_machine_profile() -> dict[str, str]:
    """Return the machine profile from environment or local ignored config.

    Environment variables take precedence so the office machine can select its
    identity without changing tracked files:
    ``FACTOR_MACHINE_PROFILE=office`` and optionally
    ``FACTOR_MACHINE_LABEL=公司电脑``.
    """

    config = _read_local_config()
    env_profile = os.environ.get("FACTOR_MACHINE_PROFILE", "").strip()
    env_label = os.environ.get("FACTOR_MACHINE_LABEL", "").strip()
    raw_profile = env_profile or config.get("machine_profile")
    if raw_profile is None or not str(raw_profile).strip():
        raise RuntimeError(
            "Machine profile is not configured. Create machine_profile.local.json "
            "or set FACTOR_MACHINE_PROFILE to home or office."
        )
    profile = _normalise_profile(raw_profile)
    raw_label = env_label
    if not raw_label and not env_profile:
        raw_label = config.get("machine_label")
    label = str(raw_label).strip() if raw_label is not None else ""
    return {
        "machine_profile": profile,
        "machine_label": label or label_for_profile(profile),
    }
