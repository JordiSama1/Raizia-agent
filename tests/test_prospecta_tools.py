from __future__ import annotations

import json
import signal
import subprocess

from tools import prospecta_tools


def install_fake_popen(monkeypatch, *, stdout, stderr="", returncode=0, seen=None):
    seen = seen if seen is not None else {}

    class FakePopen:
        pid = 12345

        def __init__(self, cmd, **kwargs):
            seen["cmd"] = cmd
            seen["kwargs"] = kwargs
            self.returncode = returncode

        def communicate(self, input=None, timeout=None):
            seen["input"] = input
            seen["timeout"] = timeout
            return stdout, stderr

    monkeypatch.setattr(prospecta_tools.subprocess, "Popen", FakePopen)
    return seen


def test_terminate_process_tree_kills_process_group(monkeypatch):
    calls = []

    class FakeProcess:
        pid = 12345

        def wait(self, timeout=None):
            calls.append(("wait", timeout))
            if len([c for c in calls if c[0] == "wait"]) == 1:
                raise subprocess.TimeoutExpired("fake", timeout)

    monkeypatch.setattr(prospecta_tools.os, "name", "posix")
    monkeypatch.setattr(prospecta_tools.os, "killpg", lambda pid, sig: calls.append(("killpg", pid, sig)))

    prospecta_tools._terminate_process_tree(FakeProcess())

    assert ("killpg", 12345, signal.SIGTERM) in calls
    assert ("killpg", 12345, signal.SIGKILL) in calls


def test_property_google_leads_builds_safe_npm_command(monkeypatch, tmp_path):
    prospecta_root = tmp_path / "prospecta"
    (prospecta_root / "tools").mkdir(parents=True)
    (prospecta_root / "node_modules" / ".bin").mkdir(parents=True)
    (prospecta_root / "package.json").write_text("{}", encoding="utf-8")
    (prospecta_root / "tools" / "property-google-leads.ts").write_text("", encoding="utf-8")
    (prospecta_root / "node_modules" / ".bin" / "tsx").write_text("", encoding="utf-8")
    monkeypatch.setenv("RAIZIA_PROSPECTA_ROOT", str(prospecta_root))

    seen = {}

    install_fake_popen(
        monkeypatch,
        stdout=json.dumps({"ok": True, "mode": "plan", "queries": []}),
        seen=seen,
    )

    result = json.loads(prospecta_tools._run_property_google_leads({
        "property": {"asset_type": "casa", "city": "Vitacura"},
        "mode": "plan",
        "max_queries": 10,
        "max_per_query": 2,
    }))

    assert result["ok"] is True
    assert seen["cmd"] == [
        str(prospecta_root / "node_modules" / ".bin" / "tsx"),
        "tools/property-google-leads.ts",
        "--json",
        "--mode",
        "plan",
        "--max-queries",
        "10",
        "--max-per-query",
        "2",
        "--concurrency",
        "4",
        "--input",
        "-",
    ]
    assert seen["kwargs"]["cwd"] == prospecta_root
    assert seen["kwargs"]["start_new_session"] is True
    assert "shell" not in seen["kwargs"]
    payload = json.loads(seen["input"])
    assert payload["property"]["city"] == "Vitacura"
    assert payload["mode"] == "plan"


def test_property_google_leads_passes_concurrency_to_cli_and_payload(monkeypatch, tmp_path):
    prospecta_root = tmp_path / "prospecta"
    (prospecta_root / "tools").mkdir(parents=True)
    (prospecta_root / "node_modules" / ".bin").mkdir(parents=True)
    (prospecta_root / "package.json").write_text("{}", encoding="utf-8")
    (prospecta_root / "tools" / "property-google-leads.ts").write_text("", encoding="utf-8")
    (prospecta_root / "node_modules" / ".bin" / "tsx").write_text("", encoding="utf-8")
    monkeypatch.setenv("RAIZIA_PROSPECTA_ROOT", str(prospecta_root))

    seen = {}

    install_fake_popen(
        monkeypatch,
        stdout=json.dumps({"ok": True, "mode": "scrape", "queries": []}),
        seen=seen,
    )

    result = json.loads(prospecta_tools._run_property_google_leads({
        "property": {"asset_type": "casa", "city": "Puerto Montt"},
        "mode": "scrape",
        "max_queries": 4,
        "max_per_query": 10,
        "concurrency": 4,
    }))

    assert result["ok"] is True
    assert seen["cmd"][seen["cmd"].index("--concurrency") + 1] == "4"
    payload = json.loads(seen["input"])
    assert payload["concurrency"] == 4


def test_property_google_leads_passes_custom_queries_to_payload(monkeypatch, tmp_path):
    prospecta_root = tmp_path / "prospecta"
    (prospecta_root / "tools").mkdir(parents=True)
    (prospecta_root / "node_modules" / ".bin").mkdir(parents=True)
    (prospecta_root / "package.json").write_text("{}", encoding="utf-8")
    (prospecta_root / "tools" / "property-google-leads.ts").write_text("", encoding="utf-8")
    (prospecta_root / "node_modules" / ".bin" / "tsx").write_text("", encoding="utf-8")
    monkeypatch.setenv("RAIZIA_PROSPECTA_ROOT", str(prospecta_root))

    seen = {}

    install_fake_popen(
        monkeypatch,
        stdout=json.dumps({"ok": True, "mode": "plan", "queries": []}),
        seen=seen,
    )

    custom_queries = [
        "hotel boutique Puerto Montt",
        {
            "query": "empresa salmonera Puerto Montt",
            "tipo": "salmonera",
            "family": "salmoneras",
            "reason": "Comprador regional ligado al ecosistema acuicola",
        },
    ]
    result = json.loads(prospecta_tools._run_property_google_leads({
        "property": {"asset_type": "casa con terreno", "city": "Puerto Montt"},
        "mode": "plan",
        "custom_queries": custom_queries,
    }))

    assert result["ok"] is True
    payload = json.loads(seen["input"])
    assert payload["custom_queries"] == custom_queries


def test_property_google_leads_schema_exposes_concurrency():
    props = prospecta_tools.PROSPECTA_PROPERTY_GOOGLE_LEADS_SCHEMA["parameters"]["properties"]

    assert props["concurrency"]["type"] == "integer"
    assert props["concurrency"]["default"] == 4
    assert props["concurrency"]["minimum"] == 1


def test_property_google_leads_schema_exposes_custom_queries_for_agent_strategy():
    schema = prospecta_tools.PROSPECTA_PROPERTY_GOOGLE_LEADS_SCHEMA
    props = schema["parameters"]["properties"]

    assert "custom_queries" in props
    assert props["custom_queries"]["type"] == "array"
    assert "think" in schema["description"].lower()
    assert "template" in schema["description"].lower()


def test_property_google_leads_accepts_harness_metadata(monkeypatch, tmp_path):
    prospecta_root = tmp_path / "prospecta"
    (prospecta_root / "tools").mkdir(parents=True)
    (prospecta_root / "node_modules" / ".bin").mkdir(parents=True)
    (prospecta_root / "package.json").write_text("{}", encoding="utf-8")
    (prospecta_root / "tools" / "property-google-leads.ts").write_text("", encoding="utf-8")
    (prospecta_root / "node_modules" / ".bin" / "tsx").write_text("", encoding="utf-8")
    monkeypatch.setenv("RAIZIA_PROSPECTA_ROOT", str(prospecta_root))

    install_fake_popen(
        monkeypatch,
        stdout=json.dumps({"ok": True, "mode": "plan", "queries": []}),
    )

    result = json.loads(prospecta_tools.registry.dispatch(
        "prospecta_property_google_leads",
        {"property": {"asset_type": "casa", "city": "Vitacura"}},
        task_id="test-task",
        tool_call_id="call_123",
    ))

    assert result["ok"] is True


def test_property_google_leads_clamps_limits_and_scrape_mode(monkeypatch, tmp_path):
    prospecta_root = tmp_path / "prospecta"
    (prospecta_root / "tools").mkdir(parents=True)
    (prospecta_root / "node_modules" / ".bin").mkdir(parents=True)
    (prospecta_root / "package.json").write_text("{}", encoding="utf-8")
    (prospecta_root / "tools" / "property-google-leads.ts").write_text("", encoding="utf-8")
    (prospecta_root / "node_modules" / ".bin" / "tsx").write_text("", encoding="utf-8")
    monkeypatch.setenv("RAIZIA_PROSPECTA_ROOT", str(prospecta_root))

    seen = {}

    install_fake_popen(
        monkeypatch,
        stdout=json.dumps({"ok": True, "mode": "scrape", "queries": []}),
        stderr="scraper log",
        seen=seen,
    )

    result = json.loads(prospecta_tools._run_property_google_leads({
        "property": {"asset_type": "casa", "city": "Vitacura"},
        "mode": "scrape",
        "max_queries": 999,
        "max_per_query": 999,
    }))

    assert result["mode"] == "scrape"
    assert result["logs"] == "scraper log"
    assert seen["cmd"][seen["cmd"].index("--mode") + 1] == "scrape"
    assert seen["cmd"][seen["cmd"].index("--max-queries") + 1] == "50"
    assert seen["cmd"][seen["cmd"].index("--max-per-query") + 1] == "100"


def test_property_google_leads_rejects_missing_property():
    result = json.loads(prospecta_tools._run_property_google_leads({}))
    assert "error" in result
    assert "property object is required" in result["error"]


def test_property_google_leads_handles_non_json_stdout(monkeypatch, tmp_path):
    prospecta_root = tmp_path / "prospecta"
    (prospecta_root / "tools").mkdir(parents=True)
    (prospecta_root / "node_modules" / ".bin").mkdir(parents=True)
    (prospecta_root / "package.json").write_text("{}", encoding="utf-8")
    (prospecta_root / "tools" / "property-google-leads.ts").write_text("", encoding="utf-8")
    (prospecta_root / "node_modules" / ".bin" / "tsx").write_text("", encoding="utf-8")
    monkeypatch.setenv("RAIZIA_PROSPECTA_ROOT", str(prospecta_root))

    install_fake_popen(monkeypatch, stdout="not-json")

    result = json.loads(prospecta_tools._run_property_google_leads({
        "property": {"asset_type": "casa", "city": "Vitacura"},
    }))

    assert "error" in result
    assert "non-JSON" in result["error"]


def test_property_google_leads_timeout_terminates_process_group(monkeypatch, tmp_path):
    prospecta_root = tmp_path / "prospecta"
    (prospecta_root / "tools").mkdir(parents=True)
    (prospecta_root / "node_modules" / ".bin").mkdir(parents=True)
    (prospecta_root / "package.json").write_text("{}", encoding="utf-8")
    (prospecta_root / "tools" / "property-google-leads.ts").write_text("", encoding="utf-8")
    (prospecta_root / "node_modules" / ".bin" / "tsx").write_text("", encoding="utf-8")
    monkeypatch.setenv("RAIZIA_PROSPECTA_ROOT", str(prospecta_root))

    calls = []

    class FakePopen:
        pid = 54321
        returncode = None

        def __init__(self, cmd, **kwargs):
            calls.append(("popen", kwargs.get("start_new_session")))

        def communicate(self, input=None, timeout=None):
            raise subprocess.TimeoutExpired("fake", timeout)

        def wait(self, timeout=None):
            calls.append(("wait", timeout))

    monkeypatch.setattr(prospecta_tools.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(prospecta_tools.os, "name", "posix")
    monkeypatch.setattr(prospecta_tools.os, "killpg", lambda pid, sig: calls.append(("killpg", pid, sig)))

    result = json.loads(prospecta_tools._run_property_google_leads({
        "property": {"asset_type": "casa", "city": "Vitacura"},
        "mode": "scrape",
    }))

    assert "timed out" in result["error"]
    assert ("popen", True) in calls
    assert ("killpg", 54321, signal.SIGTERM) in calls


def test_check_prospecta_requirements(monkeypatch, tmp_path):
    prospecta_root = tmp_path / "prospecta"
    (prospecta_root / "tools").mkdir(parents=True)
    monkeypatch.setenv("RAIZIA_PROSPECTA_ROOT", str(prospecta_root))

    assert prospecta_tools.check_prospecta_requirements() is False

    (prospecta_root / "package.json").write_text("{}", encoding="utf-8")
    (prospecta_root / "tools" / "property-google-leads.ts").write_text("", encoding="utf-8")
    assert prospecta_tools.check_prospecta_requirements() is False

    (prospecta_root / "node_modules" / ".bin").mkdir(parents=True)
    (prospecta_root / "node_modules" / ".bin" / "tsx").write_text("", encoding="utf-8")
    assert prospecta_tools.check_prospecta_requirements() is True
