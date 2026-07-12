from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Product

# Allowed source names — strict exact SKU only, no fuzzy matching.
ALLOWED_SOURCES = frozenset({"atb", "fora", "thrash", "auchan", "novus"})


class MappingValidationError(ValueError):
    """Raised when a source mapping file fails validation."""


def load_mappings(path: str | Path) -> dict[str, Any]:
    """Load and validate a source mapping JSON file.

    Returns the parsed mapping dict on success.
    Raises MappingValidationError on any violation.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    _validate_mapping_structure(data)
    return data


def validate_mappings(
    data: dict[str, Any],
    known_products: dict[str, Product] | None = None,
) -> list[str]:
    """Validate mapping file structure and content.

    Args:
        data: Parsed mapping JSON (as returned by load_mappings).
        known_products: Dict of known product_id -> Product for cross-validation.
                        If None, only structural checks are performed.

    Returns:
        List of validation error messages (empty list means valid).
    """
    errors: list[str] = []

    # --- top-level structure ---
    if not isinstance(data, dict):
        errors.append("Root must be a JSON object")
        return errors

    version = data.get("version")
    if not isinstance(version, int):
        errors.append('"version" must be an integer')

    products = data.get("products")
    if not isinstance(products, list):
        errors.append('"products" must be an array')
        return errors

    # --- source priority list ---
    source_priority = data.get("source_priority", [])
    if isinstance(source_priority, list):
        for sp in source_priority:
            if sp not in ALLOWED_SOURCES:
                errors.append(f'source_priority contains unknown source: "{sp}"')

    # --- per-product checks ---
    seen_ids: set[str] = set()

    for i, product in enumerate(products):
        if not isinstance(product, dict):
            errors.append(f"products[{i}]: expected an object, got {type(product).__name__}")
            continue

        pid = product.get("product_id")
        if not isinstance(pid, str) or not pid:
            errors.append(f"products[{i}]: missing or invalid 'product_id'")
        else:
            if pid in seen_ids:
                errors.append(f"products[{i}]: duplicate product_id '{pid}'")
            seen_ids.add(pid)

            # Cross-check against known products if provided
            if known_products is not None and pid not in known_products:
                errors.append(f"products[{i}]: product_id '{pid}' not found in seed_products")

        mappings = product.get("mappings")
        if not isinstance(mappings, dict):
            errors.append(f"products[{i}] ('{pid}'): missing or invalid 'mappings' object")
            continue

        for source_name, mapping in mappings.items():
            if source_name not in ALLOWED_SOURCES:
                errors.append(
                    f"products[{i}] ('{pid}'): source '{source_name}' is not allowed "
                    f"(allowed: {sorted(ALLOWED_SOURCES)})"
                )

            if not isinstance(mapping, dict):
                errors.append(
                    f"products[{i}] ('{pid}', source '{source_name}'): mapping must be an object"
                )
                continue

            # Every mapping must have confidence
            if "confidence" not in mapping:
                errors.append(
                    f"products[{i}] ('{pid}', source '{source_name}'): missing 'confidence'"
                )

            # Must have either url or source_product_id / query
            has_url = "url" in mapping and isinstance(mapping["url"], str) and mapping["url"]
            has_spid = (
                "source_product_id" in mapping
                and isinstance(mapping["source_product_id"], str)
                and mapping["source_product_id"]
            )
            has_query = (
                "query" in mapping and isinstance(mapping["query"], str) and mapping["query"]
            )
            if not has_url and not has_spid and not has_query:
                errors.append(
                    f"products[{i}] ('{pid}', source '{source_name}'): "
                    "must have 'url' and/or 'source_product_id'/'query'"
                )

    return errors


def check_mappings(path: str | Path, seed_path: str | Path | None = None) -> list[str]:
    """Convenience: load mapping file and validate against seed products.

    Args:
        path: Path to mapping JSON file.
        seed_path: Optional path to seed_products.json for cross-validation.

    Returns:
        List of validation errors (empty = valid).
    """
    try:
        data = load_mappings(path)
    except (json.JSONDecodeError, FileNotFoundError, MappingValidationError) as exc:
        return [str(exc)]

    known: dict[str, Product] | None = None
    if seed_path is not None:
        try:
            seed_data = json.loads(Path(seed_path).read_text(encoding="utf-8"))
            known = {item["id"]: Product(**item) for item in seed_data}
        except Exception as exc:
            return [f"Could not load seed products from {seed_path}: {exc}"]

    return validate_mappings(data, known)


def _validate_mapping_structure(data: dict[str, Any]) -> None:
    """Strict structural validation — raises MappingValidationError on first violation."""
    errors = validate_mappings(data)
    if errors:
        raise MappingValidationError("\n".join(errors))
