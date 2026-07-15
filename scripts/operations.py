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
