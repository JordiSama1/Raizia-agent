from pathlib import Path


SKILL_PATH = Path(__file__).resolve().parents[1] / "skills" / "productivity" / "prospecta-real-estate-ops" / "SKILL.md"


def test_prospecta_real_estate_ops_skill_documents_raizia_pipeline():
    content = SKILL_PATH.read_text(encoding="utf-8")
    lower = content.lower()

    assert content.startswith("---\n")
    assert "name: prospecta-real-estate-ops" in content
    assert "prospecta_property_google_leads" in content
    assert "custom_queries" in content
    assert "allow_templates=true" in content
    assert "deterministic scraper" in lower
    assert "raizia classifies" in lower
    assert "google maps" in lower
    assert "linkedin" in lower
    assert "write to everyone" in lower
    assert "most relevant" in lower
    assert "never send" in lower
