from __future__ import annotations

import json
import subprocess

from tools import prospecta_tools


def test_property_google_leads_builds_safe_npm_command(monkeypatch, tmp_path):
    prospecta_root = tmp_path / "prospecta"
    (prospecta_root / "tools").mkdir(parents=True)
    (prospecta_root / "node_modules" / ".bin").mkdir(parents=True)
    (prospecta_root / "package.json").write_text("{}", encoding="utf-8")
    (prospecta_root / "tools" / "property-google-leads.ts").write_text("", encoding="utf-8")
    (prospecta_root / "node_modules" / ".bin" / "tsx").write_text("", encoding="utf-8")
    monkeypatch.setenv("RAIZIA_PROSPECTA_ROOT", str(prospecta_root))

    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps({"ok": True, "mode": "plan", "queries": []}),
            stderr="",
        )

    monkeypatch.setattr(prospecta_tools.subprocess, "run", fake_run)

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
        "--input",
        "-",
    ]
    assert seen["kwargs"]["cwd"] == prospecta_root
    assert "shell" not in seen["kwargs"]
    payload = json.loads(seen["kwargs"]["input"])
    assert payload["property"]["city"] == "Vitacura"
    assert payload["mode"] == "plan"


def test_property_google_leads_clamps_limits_and_scrape_mode(monkeypatch, tmp_path):
    prospecta_root = tmp_path / "prospecta"
    (prospecta_root / "tools").mkdir(parents=True)
    (prospecta_root / "node_modules" / ".bin").mkdir(parents=True)
    (prospecta_root / "package.json").write_text("{}", encoding="utf-8")
    (prospecta_root / "tools" / "property-google-leads.ts").write_text("", encoding="utf-8")
    (prospecta_root / "node_modules" / ".bin" / "tsx").write_text("", encoding="utf-8")
    monkeypatch.setenv("RAIZIA_PROSPECTA_ROOT", str(prospecta_root))

    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps({"ok": True, "mode": "scrape", "queries": []}),
            stderr="scraper log",
        )

    monkeypatch.setattr(prospecta_tools.subprocess, "run", fake_run)

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

    monkeypatch.setattr(
        prospecta_tools.subprocess,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, 0, stdout="not-json", stderr=""),
    )

    result = json.loads(prospecta_tools._run_property_google_leads({
        "property": {"asset_type": "casa", "city": "Vitacura"},
    }))

    assert "error" in result
    assert "non-JSON" in result["error"]


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
