#!/usr/bin/env python3
"""Prospecta toolset for Raizia.

The agent harness stays close to upstream Hermes. Real-estate domain logic
lives in ``packages/prospecta`` and is invoked through JSON CLIs.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict

from tools.registry import registry, tool_error, tool_result


TOOLSET = "prospecta"
DEFAULT_TIMEOUT_SECONDS = 900


def _platform_root() -> Path:
    return Path(__file__).resolve().parents[3]


def prospecta_root() -> Path:
    configured = os.getenv("RAIZIA_PROSPECTA_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return _platform_root() / "packages" / "prospecta"


def check_prospecta_requirements() -> bool:
    root = prospecta_root()
    return (
        (root / "package.json").exists()
        and (root / "tools" / "property-google-leads.ts").exists()
        and (root / "node_modules" / ".bin" / "tsx").exists()
    )


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _mode(value: Any) -> str:
    return "scrape" if str(value or "").strip().lower() == "scrape" else "plan"


def _run_property_google_leads(args: Dict[str, Any]) -> str:
    prop = args.get("property")
    if not isinstance(prop, dict):
        return tool_error("property object is required")

    mode = _mode(args.get("mode"))
    max_queries = _bounded_int(args.get("max_queries"), 10, 1, 50)
    max_per_query = _bounded_int(args.get("max_per_query"), 2, 1, 100)

    payload = {
        "property": prop,
        "mode": mode,
        "max_queries": max_queries,
        "max_per_query": max_per_query,
    }

    root = prospecta_root()
    tsx_bin = root / "node_modules" / ".bin" / "tsx"
    if not tsx_bin.exists():
        return tool_error("Prospecta dependencies are missing. Run npm install in packages/prospecta.")

    cmd = [
        str(tsx_bin),
        "tools/property-google-leads.ts",
        "--json",
        "--mode",
        mode,
        "--max-queries",
        str(max_queries),
        "--max-per-query",
        str(max_per_query),
        "--input",
        "-",
    ]

    try:
        completed = subprocess.run(
            cmd,
            cwd=root,
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            capture_output=True,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError as exc:
        return tool_error(f"Could not execute npm: {exc}")
    except subprocess.TimeoutExpired:
        return tool_error(f"Prospecta Google lead tool timed out after {DEFAULT_TIMEOUT_SECONDS}s")

    if completed.returncode != 0:
        return tool_error(
            "Prospecta Google lead tool failed",
            returncode=completed.returncode,
            stderr=completed.stderr[-4000:],
            stdout=completed.stdout[-4000:],
        )

    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return tool_error(
            f"Prospecta returned non-JSON stdout: {exc}",
            stdout=completed.stdout[-4000:],
            stderr=completed.stderr[-4000:],
        )

    if isinstance(parsed, dict) and completed.stderr:
        parsed.setdefault("logs", completed.stderr[-4000:])
    return tool_result(parsed)


PROSPECTA_PROPERTY_GOOGLE_LEADS_SCHEMA = {
    "name": "prospecta_property_google_leads",
    "description": (
        "Plan or run a safe Prospecta Google Maps lead search for one real-estate "
        "property. Default mode is plan: it generates ranked Google Maps query "
        "combinations without opening a browser. Scrape mode runs Playwright with "
        "explicit caps and writes leads to Prospecta SQLite. This tool never sends "
        "WhatsApp, Chatwoot, LinkedIn, or outbound messages."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "property": {
                "type": "object",
                "description": (
                    "Property brief. Required fields: city and asset_type. Useful "
                    "fields: operation, address, price_uf, rent_uf, built_m2, "
                    "land_m2, bedrooms, bathrooms, parking, highlights."
                ),
            },
            "mode": {
                "type": "string",
                "enum": ["plan", "scrape"],
                "default": "plan",
                "description": "Use plan first. Scrape opens Google Maps and saves leads.",
            },
            "max_queries": {
                "type": "integer",
                "default": 10,
                "minimum": 1,
                "maximum": 50,
                "description": "Maximum ranked query combinations to generate or run.",
            },
            "max_per_query": {
                "type": "integer",
                "default": 2,
                "minimum": 1,
                "maximum": 100,
                "description": "Google Maps result cap per query in scrape mode.",
            },
        },
        "required": ["property"],
    },
}


registry.register(
    name="prospecta_property_google_leads",
    toolset=TOOLSET,
    schema=PROSPECTA_PROPERTY_GOOGLE_LEADS_SCHEMA,
    handler=_run_property_google_leads,
    check_fn=check_prospecta_requirements,
    emoji="🏠",
    max_result_size_chars=60_000,
)
