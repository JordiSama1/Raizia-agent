#!/usr/bin/env python3
"""Prospecta toolset for Raizia.

The agent harness stays close to upstream Hermes. Real-estate domain logic
lives in ``packages/prospecta`` and is invoked through JSON CLIs.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
from pathlib import Path
from typing import Any, Dict, NamedTuple

from tools.registry import registry, tool_error, tool_result


TOOLSET = "prospecta"
DEFAULT_TIMEOUT_SECONDS = 900


class CommandResult(NamedTuple):
    returncode: int
    stdout: str
    stderr: str


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


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _custom_queries(value: Any) -> list[Any]:
    if not isinstance(value, list):
        return []

    allowed_object_keys = {
        "query",
        "tipo",
        "pitch",
        "family",
        "intent",
        "score",
        "reason",
        "city",
    }
    queries: list[Any] = []
    for item in value:
        if isinstance(item, str):
            query = item.strip()
            if query:
                queries.append(query)
            continue

        if not isinstance(item, dict):
            continue
        query = str(item.get("query") or "").strip()
        if not query:
            continue
        cleaned = {key: item[key] for key in allowed_object_keys if key in item}
        cleaned["query"] = query
        queries.append(cleaned)

    return queries[:50]


def _terminate_process_tree(proc: subprocess.Popen) -> None:
    try:
        if os.name == "posix":
            os.killpg(proc.pid, signal.SIGTERM)
        else:
            proc.terminate()
    except ProcessLookupError:
        return
    except Exception:
        try:
            proc.kill()
        except Exception:
            return

    try:
        proc.wait(timeout=5)
        return
    except subprocess.TimeoutExpired:
        pass

    try:
        if os.name == "posix":
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
    except ProcessLookupError:
        return
    except Exception:
        return
    try:
        proc.wait(timeout=5)
    except Exception:
        return


def _run_json_command(cmd: list[str], root: Path, payload: Dict[str, Any]) -> CommandResult:
    proc = subprocess.Popen(
        cmd,
        cwd=root,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=(os.name == "posix"),
    )
    try:
        stdout, stderr = proc.communicate(
            json.dumps(payload, ensure_ascii=False),
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        _terminate_process_tree(proc)
        raise
    except KeyboardInterrupt:
        _terminate_process_tree(proc)
        raise
    return CommandResult(proc.returncode, stdout or "", stderr or "")


def _run_property_google_leads(args: Dict[str, Any], **_metadata: Any) -> str:
    prop = args.get("property")
    if not isinstance(prop, dict):
        return tool_error("property object is required")

    mode = _mode(args.get("mode"))
    max_queries = _bounded_int(args.get("max_queries"), 10, 1, 50)
    max_per_query = _bounded_int(args.get("max_per_query"), 2, 1, 100)
    concurrency = _bounded_int(args.get("concurrency"), 4, 1, 8)
    custom_queries = _custom_queries(args.get("custom_queries"))
    allow_templates = _truthy(args.get("allow_templates"))

    if not custom_queries and not allow_templates:
        return tool_error(
            "custom_queries are required by default. Raizia must build a contextual "
            "buyer strategy before running Prospecta; pass allow_templates=true only "
            "for an explicit template fallback.",
            strategy_required=True,
            allowed_next_action="generate_custom_queries",
        )

    payload = {
        "property": prop,
        "mode": mode,
        "max_queries": max_queries,
        "max_per_query": max_per_query,
        "concurrency": concurrency,
    }
    if custom_queries:
        payload["custom_queries"] = custom_queries
    if allow_templates:
        payload["allow_templates"] = True

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
        "--concurrency",
        str(concurrency),
        "--input",
        "-",
    ]

    try:
        completed = _run_json_command(cmd, root, payload)
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
        "property. custom_queries are required by default: Raizia must think through "
        "a contextual buyer strategy first and pass property-specific searches. "
        "Built-in templates are only an explicit fallback when allow_templates=true. "
        "Default mode is plan: it returns ranked Google Maps query combinations "
        "without opening a browser. Scrape mode runs Playwright with explicit caps "
        "and writes leads to Prospecta SQLite. "
        "This tool never sends WhatsApp, Chatwoot, LinkedIn, or outbound messages."
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
            "concurrency": {
                "type": "integer",
                "default": 4,
                "minimum": 1,
                "maximum": 8,
                "description": (
                    "Parallel Google Maps target workers in scrape mode. Keep 3-4 "
                    "for stable runs; higher values increase CAPTCHA/bot-block risk."
                ),
            },
            "custom_queries": {
                "type": "array",
                "description": (
                    "Agent-generated Google Maps searches for this exact property. "
                    "Required by default. Use this when reasoning finds contextual buyer segments such as "
                    "tourism, salmoneras, logistics, local family companies, or other "
                    "regional demand drivers. If omitted, the tool refuses to run unless "
                    "allow_templates is explicitly true."
                ),
                "items": {
                    "anyOf": [
                        {"type": "string"},
                        {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"},
                                "tipo": {"type": "string"},
                                "pitch": {"type": "string"},
                                "family": {"type": "string"},
                                "intent": {
                                    "type": "string",
                                    "enum": [
                                        "buyer_candidate",
                                        "channel_partner",
                                        "service_provider",
                                        "low_fit",
                                    ],
                                },
                                "score": {
                                    "type": "integer",
                                    "minimum": 1,
                                    "maximum": 100,
                                },
                                "reason": {"type": "string"},
                                "city": {"type": "string"},
                            },
                            "required": ["query"],
                        },
                    ],
                },
                "maxItems": 50,
            },
            "allow_templates": {
                "type": "boolean",
                "default": False,
                "description": (
                    "Explicit escape hatch for Prospecta's built-in generic templates. "
                    "Leave false for Raizia product flows; set true only when the user "
                    "asks for template fallback or a low-context smoke test."
                ),
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
