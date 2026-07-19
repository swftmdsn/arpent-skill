"""Load the Arpent operation contract without external dependencies."""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from . import frontmatter as fmlib

DEFAULT_OPERATIONS_PATH = Path(__file__).with_name("operations.yaml")
OPERATIONS_VERSION = "0.9.0"
ROUTING_OVERLAY_KEYS = (
    "type_subfolders", "type_overrides", "status_type_overrides", "zero_field_routes",
)
CONFIRMATION_POLICIES = ("always", "explicit-intent", "never")


def default_operations_text() -> str:
    return DEFAULT_OPERATIONS_PATH.read_text(encoding="utf-8")


def load_operations(path: str | Path | None = None) -> dict:
    source = Path(path) if path else DEFAULT_OPERATIONS_PATH
    data = fmlib.parse_frontmatter_block(source.read_text(encoding="utf-8"))
    if data.get("version") != OPERATIONS_VERSION:
        raise ValueError(
            f"operations.yaml version must be {OPERATIONS_VERSION}; older contracts are unsupported."
        )
    return data


@lru_cache(maxsize=1)
def default_operations() -> dict:
    return load_operations(DEFAULT_OPERATIONS_PATH)


def routing_contract(path: str | Path | None = None) -> dict:
    packaged = default_operations().get("routing") or {}
    if not isinstance(packaged, dict):
        raise ValueError("Packaged operations.yaml has no valid routing contract.")
    if path is None:
        contract = deepcopy(packaged)
        _validate_route_paths(contract)
        return contract

    local_data = load_operations(path)
    mirrored = local_data.get("routing") or {}
    if not isinstance(mirrored, dict):
        raise ValueError("Vault operations.yaml has no valid routing contract.")

    merged = deepcopy(packaged)
    overlays = local_data.get("routing_overrides") or {}
    if not isinstance(overlays, dict):
        raise ValueError("Vault routing_overrides must be a mapping.")
    unknown = set(overlays) - set(ROUTING_OVERLAY_KEYS)
    if unknown:
        raise ValueError(f"Unknown vault routing override keys: {', '.join(sorted(unknown))}")
    for key in ROUTING_OVERLAY_KEYS:
        overlay = overlays.get(key)
        if overlay is None:
            continue
        if not isinstance(overlay, dict):
            raise ValueError(f"Vault routing overlay '{key}' must be a mapping.")
        current = dict(merged.get(key) or {})
        current.update(deepcopy(overlay))
        merged[key] = current
    _validate_route_paths(merged)
    return merged


def confirmation_policy(path: str | Path | None = None) -> dict:
    """Return the validated per-vault confirmation policy."""
    data = default_operations() if path is None else load_operations(path)
    policy = data.get("confirmation")
    if policy is None:
        raise ValueError("operations.yaml requires a confirmation section.")
    if not isinstance(policy, dict):
        raise ValueError("operations.yaml confirmation must be a mapping.")
    if "mode" in policy:
        raise ValueError("confirmation.mode is unsupported; use confirmation.policy.")
    selected = policy.get("policy")
    threshold = policy.get("bulk_threshold")
    if selected not in CONFIRMATION_POLICIES:
        raise ValueError(
            "confirmation.policy must be one of: " + ", ".join(CONFIRMATION_POLICIES)
        )
    if type(threshold) is not int or threshold < 1:
        raise ValueError("confirmation.bulk_threshold must be a positive integer.")
    return {"policy": selected, "bulk_threshold": threshold}


def operation_is_high_impact(operation: str, path: str | Path | None = None) -> bool:
    """Return whether explicit-intent policy still requires confirmation."""
    packaged = default_operations().get("operations") or {}
    if not isinstance(packaged, dict):
        raise ValueError("Packaged operations.yaml has no valid operation inventory.")
    local = load_operations(path).get("operations") or {} if path is not None else {}
    if not isinstance(local, dict):
        raise ValueError("Vault operations.yaml operation inventory must be a mapping.")
    entry = local.get(operation, packaged.get(operation))
    if not isinstance(entry, dict):
        raise ValueError(f"Unknown operation '{operation}'.")
    if "confirmation" in entry:
        raise ValueError(
            f"operations.{operation}.confirmation is unsupported; use high_impact."
        )
    high_impact = entry.get("high_impact", False)
    if type(high_impact) is not bool:
        raise ValueError(f"operations.{operation}.high_impact must be a boolean.")
    return high_impact


def requires_confirmation(operation: str, *, count=1,
                           path: str | Path | None = None) -> bool:
    """Apply the configured policy to one explicit CLI operation."""
    if type(count) is not int or count < 1:
        raise ValueError("confirmation item count must be a positive integer.")
    policy = confirmation_policy(path)
    high_impact = operation_is_high_impact(operation, path)
    if policy["policy"] == "never":
        return False
    if policy["policy"] == "always":
        return True
    return count >= policy["bulk_threshold"] or high_impact


def _validate_route_paths(routing: dict) -> None:
    for key, value in (routing.get("type_subfolders") or {}).items():
        _validate_relative_route(value, f"type_subfolders.{key}", single_component=True)
    for group in ("type_overrides", "status_type_overrides"):
        for key, rule in (routing.get(group) or {}).items():
            if not isinstance(rule, dict):
                raise ValueError(f"Routing rule '{group}.{key}' must be a mapping.")
            _validate_relative_route(rule.get("bucket"), f"{group}.{key}.bucket")
    for key, value in (routing.get("zero_field_routes") or {}).items():
        _validate_relative_route(value, f"zero_field_routes.{key}")


def _validate_relative_route(value, label: str, *, single_component=False) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Routing path '{label}' must be a non-empty string.")
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"Routing path '{label}' must stay inside the vault.")
    if single_component and len(candidate.parts) != 1:
        raise ValueError(f"Routing subfolder '{label}' must be one folder name.")
