"""Unit tests for src.ingest.attack_loader using a minimal STIX fixture."""
import json
import tempfile
from pathlib import Path

import pytest

from src.ingest.attack_loader import _attck_url, _get_technique_id, load_attack_documents

# Minimal STIX bundle with one technique, one mitigation, one relationship
MINIMAL_STIX: dict = {
    "type": "bundle",
    "id": "bundle--test",
    "objects": [
        {
            "type": "attack-pattern",
            "id": "attack-pattern--aaa",
            "name": "Command and Scripting Interpreter",
            "description": "Adversaries may abuse command and script interpreters.",
            "x_mitre_detection": "Monitor process execution logs.",
            "kill_chain_phases": [
                {"kill_chain_name": "mitre-attack", "phase_name": "execution"}
            ],
            "external_references": [
                {"source_name": "mitre-attack", "external_id": "T1059", "url": "https://attack.mitre.org/techniques/T1059"}
            ],
            "revoked": False,
            "x_mitre_deprecated": False,
            "modified": "2023-10-04T12:00:00.000Z",
        },
        {
            "type": "attack-pattern",
            "id": "attack-pattern--bbb",
            "name": "Revoked Technique",
            "description": "Should be skipped.",
            "external_references": [
                {"source_name": "mitre-attack", "external_id": "T9999"}
            ],
            "kill_chain_phases": [],
            "revoked": True,
            "modified": "2020-01-01T00:00:00.000Z",
        },
        {
            "type": "course-of-action",
            "id": "course-of-action--ccc",
            "name": "Disable or Remove Feature or Program",
            "description": "Remove or deny access to unnecessary programs.",
        },
        {
            "type": "relationship",
            "id": "relationship--ddd",
            "relationship_type": "mitigates",
            "source_ref": "course-of-action--ccc",
            "target_ref": "attack-pattern--aaa",
        },
    ],
}


@pytest.fixture
def mitre_dir(tmp_path: Path) -> Path:
    """Create data/raw/mitre/ with the minimal STIX fixture."""
    mitre = tmp_path / "mitre"
    mitre.mkdir()
    (mitre / "enterprise-attack.json").write_text(
        json.dumps(MINIMAL_STIX), encoding="utf-8"
    )
    return tmp_path  # raw_dir is the parent


def test_get_technique_id() -> None:
    obj = MINIMAL_STIX["objects"][0]
    assert _get_technique_id(obj) == "T1059"


def test_get_technique_id_missing() -> None:
    assert _get_technique_id({"external_references": []}) is None


def test_attck_url_technique() -> None:
    assert _attck_url("T1059") == "https://attack.mitre.org/techniques/T1059/"


def test_attck_url_subtechnique() -> None:
    assert _attck_url("T1059.001") == "https://attack.mitre.org/techniques/T1059/001/"


def test_load_attack_documents(mitre_dir: Path) -> None:
    docs = load_attack_documents(mitre_dir)

    # Only the non-revoked technique should be loaded
    assert len(docs) == 1

    doc = docs[0]
    assert doc.doc_id == "mitre-T1059"
    assert doc.source == "mitre"
    assert doc.title == "Command and Scripting Interpreter (T1059)"
    assert doc.section == "execution"
    assert doc.date == "2023-10-04"
    assert "attack.mitre.org/techniques/T1059/" in doc.url

    # Text should include all the composite fields
    assert "Tactics: execution" in doc.text
    assert "Adversaries may abuse" in doc.text
    assert "Disable or Remove Feature" in doc.text   # mitigation
    assert "Monitor process execution" in doc.text   # detection


def test_load_attack_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_attack_documents(tmp_path)
