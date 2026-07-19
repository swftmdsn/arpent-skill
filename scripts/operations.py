"""Load the Arpent operation contract without external dependencies."""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from . import frontmatter as fmlib

DEFAULT_OPERATIONS_PATH = Path(__file__).with_name("operations.yaml")
ROUTING_OVERLAY_KEYS = (
    "type_subfolders", "type_overrides", "status_type_overrides", "zero_field_routes",
)
CONFIRMATION_MODES = ("always", "explicit-intent", "never")
CONFIRMATION_CLASSES = ("read-only", "additive", "targeted", "high-impact")


def default_operations_text() -> str:
    return DEFAULT_OPERATIONS_PATH.read_text(encoding="utf-8")


def load_operations(path: str | Path | None = None) -> dict:
    source = Path(path) if path else DEFAULT_OPERATIONS_PATH
    return fmlib.parse_frontmatter_block(source.read_text(encoding="utf-8"))


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
    """Return the validated per-vault confirmation policy.

    Existing vault contracts without this section retain the conservative
    `always` behavior. Newly initialized vaults mirror the packaged default.
    """
    data = default_operations() if path is None else load_operations(path)
    policy = data.get("confirmation")
    if policy is None:
        return {"mode": "always", "bulk_threshold": 5}
    if not isinstance(policy, dict):
        raise ValueError("operations.yaml confirmation must be a mapping.")
    mode = policy.get("mode")
    threshold = policy.get("bulk_threshold")
    if mode not in CONFIRMATION_MODES:
        raise ValueError(
            "confirmation.mode must be one of: " + ", ".join(CONFIRMATION_MODES)
        )
    if type(threshold) is not int or threshold < 1:
        raise ValueError("confirmation.bulk_threshold must be a positive integer.")
    return {"mode": mode, "bulk_threshold": threshold}


def operation_confirmation_class(operation: str, path: str | Path | None = None) -> str:
    """Return the operation's confirmation class from the canonical registry."""
    packaged = default_operations().get("operations") or {}
    local = load_operations(path).get("operations") or {} if path is not None else {}
    entry = local.get(operation, packaged.get(operation))
    if not isinstance(entry, dict):
        raise ValueError(f"Unknown operation '{operation}'.")
    confirmation_class = entry.get("confirmation", "targeted")
    if confirmation_class not in CONFIRMATION_CLASSES:
        raise ValueError(
            f"operations.{operation}.confirmation must be one of: "
            + ", ".join(CONFIRMATION_CLASSES)
        )
    return confirmation_class


def requires_confirmation(operation: str, *, count=1, explicit_intent=True,
                          path: str | Path | None = None) -> bool:
    """Apply the configured policy to one planned operation."""
    if type(count) is not int or count < 1:
        raise ValueError("confirmation item count must be a positive integer.")
    policy = confirmation_policy(path)
    confirmation_class = operation_confirmation_class(operation, path)
    if policy["mode"] == "never":
        return False
    if policy["mode"] == "always":
        return True
    return (
        not explicit_intent
        or count >= policy["bulk_threshold"]
        or confirmation_class == "high-impact"
    )


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
