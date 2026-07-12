from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from brp.api.app import create_app
from brp.security import SecuritySettings

ROOT = Path(__file__).resolve().parents[3]
HEADERS = {"X-BRP-Actor": "maker-a"}

PLPGSQL = """CREATE FUNCTION eligibility(age integer)
RETURNS text AS $$
BEGIN
  IF age < 18 THEN RETURN '미성년';
  ELSE RETURN '가입 가능';
  END IF;
END;
$$ LANGUAGE plpgsql;
"""

HTML = """<form id="eligibility" aria-label="가입 검증">
<input id="age" name="age" type="number" data-rule-type="integer"
       min="18" data-error-min="미성년">
<script>globalThis.mustNeverRun = true;</script>
</form>"""

DRL = """rule "under-age"
when
  Applicant(age < 18)
then
  result.setEligible(false);
  result.setReasonCode("미성년");
end

rule "default"
when
  Applicant()
then
  result.setEligible(true);
  result.setReasonCode("가입 가능");
end
"""


def client() -> TestClient:
    return TestClient(create_app(security=SecuritySettings.local_development()))


def extraction_payload(adapter: str, content: str, filename: str) -> dict[str, str]:
    return {
        "adapter": adapter,
        "content": content,
        "filename": filename,
        "revision": "local-ui-test",
        "connectionAlias": "LOCAL_INLINE",
        "schemaName": "public",
        "objectName": "eligibility",
    }


def test_catalog_and_preflight_are_deterministic_secret_free() -> None:
    api = client()
    catalog = api.get("/orchestration/catalog")
    assert catalog.status_code == 200
    document = catalog.json()
    assert document["evidenceLabel"] == "LOCAL_PREVIEW_NON_AUTHORITATIVE"
    assert document["persistent"] is False
    assert set(document["adapters"]) >= {
        "db-postgres-stored-object",
        "ui-html-validation",
        "engine-native",
        "engine-dmn",
    }
    assert isinstance(document["hostInventory"]["dotnet"], bool)

    profile = yaml.safe_load((ROOT / "config/sites/fixture.yaml").read_text(encoding="utf-8"))
    response = api.post(
        "/orchestration/preflight",
        json={
            "profiles": [profile],
            "inventory": {
                "java": True,
                "dotnet": False,
                "joern": True,
                "zen": True,
                "postgres": True,
                "sqlite": True,
            },
        },
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["reports"][0]["ready"] is True
    assert "BRP_DATABASE_URL" not in response.text


def test_extraction_requires_maker_and_runs_stored_ui_and_drl_without_persistence() -> None:
    api = client()
    payload = extraction_payload("db-postgres-stored-object", PLPGSQL, "eligibility.sql")
    assert api.post("/orchestration/extract", json=payload).status_code == 401

    stored = api.post("/orchestration/extract", json=payload, headers=HEADERS)
    assert stored.status_code == 200, stored.text
    stored_json = stored.json()
    assert stored_json["persistent"] is False
    assert stored_json["batch"]["decisions"][0]["content"]["defaultOutput"] == {
        "result": "가입 가능"
    }

    ui = api.post(
        "/orchestration/extract",
        json=extraction_payload("ui-html-validation", HTML, "eligibility.html"),
        headers=HEADERS,
    )
    assert ui.status_code == 200, ui.text
    assert ui.json()["batch"]["decisions"][0]["content"]["rules"][0]["then"][1]["value"] == "미성년"
    assert ui.json()["batch"]["unmappable"][0]["reasonCode"] == "UNSUPPORTED_UI_SCRIPT"

    drl = api.post(
        "/orchestration/extract",
        json=extraction_payload("engine-native", DRL, "eligibility.drl"),
        headers=HEADERS,
    )
    assert drl.status_code == 200, drl.text
    assert (
        drl.json()["batch"]["decisions"][0]["content"]["rules"][0]["then"][1]["value"] == "미성년"
    )


def test_candidate_can_generate_dmn_and_csharp_non_authoritative_previews() -> None:
    api = client()
    extracted = api.post(
        "/orchestration/extract",
        json=extraction_payload("db-postgres-stored-object", PLPGSQL, "eligibility.sql"),
        headers=HEADERS,
    ).json()
    content = extracted["batch"]["decisions"][0]["content"]

    dmn = api.post(
        "/orchestration/generate",
        json={"generator": "dmn-export", "content": content},
        headers=HEADERS,
    )
    assert dmn.status_code == 200, dmn.text
    assert dmn.json()["authoritative"] is False
    assert "<decisionTable" in dmn.json()["content"]
    assert dmn.json()["contentHash"]

    csharp = api.post(
        "/orchestration/generate",
        json={
            "generator": "csharp-source",
            "content": content,
            "csharpNamespace": "Brp.LocalPreview",
        },
        headers=HEADERS,
    )
    assert csharp.status_code == 200, csharp.text
    result = csharp.json()
    assert result["authoritative"] is False
    assert "public static class EligibilityDecision" in result["content"]
    assert result["compileEvidence"]["status"] in {"COMPILE_NOT_RUN", "COMPILED"}


def test_unsafe_filename_and_mismatched_extension_are_rejected() -> None:
    api = client()
    unsafe = api.post(
        "/orchestration/extract",
        json=extraction_payload("ui-html-validation", HTML, "../unsafe.html"),
        headers=HEADERS,
    )
    assert unsafe.status_code == 422
    assert "safe basename" in unsafe.json()["detail"]

    mismatch = api.post(
        "/orchestration/extract",
        json=extraction_payload("engine-dmn", "<definitions/>", "rules.txt"),
        headers=HEADERS,
    )
    assert mismatch.status_code == 422
    assert "extension" in mismatch.json()["detail"]
