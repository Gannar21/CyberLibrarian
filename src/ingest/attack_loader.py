"""
Load MITRE ATT&CK Enterprise data from data/raw/mitre/enterprise-attack.json.

One Document per technique (including sub-techniques).
Revoked and deprecated objects are skipped.

doc_id  = "mitre-<technique_id>"
          e.g. "mitre-T1059"  or  "mitre-T1059.001"

title   = "<technique_name> (<technique_id>)"
          e.g. "Command and Scripting Interpreter (T1059)"

source  = "mitre"

section = tactic name (first kill-chain phase listed)
          e.g. "execution"  (kept lowercase to match ATT&CK phase_name values)

date    = last-modified date from the STIX object's 'modified' field (ISO prefix)

url     = https://attack.mitre.org/techniques/<technique_id>/
          sub-techniques use slash notation: /techniques/T1059/001/

text    = composite block:
            Technique heading
            Tactics
            Description
            Mitigations (name + first 500 chars of description)
            Detection
"""
from __future__ import annotations

import json
from pathlib import Path

from src.common.schemas import Document

ATTACK_JSON = "enterprise-attack.json"


def _attck_url(technique_id: str) -> str:
    """Build the ATT&CK website URL for a technique or sub-technique."""
    if "." in technique_id:
        parent, sub = technique_id.split(".", 1)
        return f"https://attack.mitre.org/techniques/{parent}/{sub}/"
    return f"https://attack.mitre.org/techniques/{technique_id}/"


def _get_technique_id(obj: dict) -> str | None:
    """Return the ATT&CK ID (T-number) from external_references, or None."""
    for ref in obj.get("external_references", []):
        if ref.get("source_name") == "mitre-attack":
            ext_id = ref.get("external_id", "")
            if ext_id.startswith("T"):
                return ext_id
    return None


def _build_text(
    name: str,
    technique_id: str,
    tactics: list[str],
    description: str,
    mitigations: list[tuple[str, str]],
    detection: str,
) -> str:
    """Build a single coherent text block for a technique Document."""
    lines: list[str] = [
        f"{name} ({technique_id})",
        "",
        f"Tactics: {', '.join(tactics) if tactics else 'none'}",
        "",
        "Description:",
        description.strip() if description else "(no description)",
    ]

    if mitigations:
        lines += ["", "Mitigations:"]
        for m_name, m_desc in mitigations:
            # Trim very long mitigation descriptions to keep documents focused
            short_desc = m_desc.strip()[:500] if m_desc else ""
            lines.append(f"- {m_name}: {short_desc}")

    if detection and detection.strip():
        lines += ["", "Detection:", detection.strip()]

    return "\n".join(lines)


def load_attack_documents(raw_dir: Path) -> list[Document]:
    """Parse enterprise-attack.json and return one Document per technique."""
    json_path = raw_dir / "mitre" / ATTACK_JSON
    if not json_path.exists():
        raise FileNotFoundError(
            f"ATT&CK STIX file not found: {json_path}\n"
            "Run  python data/download_corpus.py  first."
        )

    print(f"  attack_loader: parsing {json_path.name} (this may take a few seconds)...")
    with open(json_path, encoding="utf-8") as fh:
        bundle = json.load(fh)

    objects = bundle.get("objects", [])

    # Index all objects by STIX id for relationship lookups
    by_id: dict[str, dict] = {obj["id"]: obj for obj in objects if "id" in obj}

    # Index mitigations by STIX id (type: course-of-action)
    mitigations_by_id: dict[str, dict] = {
        obj["id"]: obj
        for obj in objects
        if obj.get("type") == "course-of-action"
    }

    # Build map: technique_stix_id → list of mitigation dicts
    technique_mitigations: dict[str, list[dict]] = {}
    for obj in objects:
        if obj.get("type") != "relationship":
            continue
        if obj.get("relationship_type") != "mitigates":
            continue
        target = obj.get("target_ref", "")
        source = obj.get("source_ref", "")
        if source in mitigations_by_id:
            technique_mitigations.setdefault(target, []).append(mitigations_by_id[source])

    docs: list[Document] = []
    for obj in objects:
        if obj.get("type") != "attack-pattern":
            continue
        if obj.get("revoked", False) or obj.get("x_mitre_deprecated", False):
            continue

        technique_id = _get_technique_id(obj)
        if not technique_id:
            continue

        name: str = obj.get("name", "")
        description: str = obj.get("description", "")
        detection: str = obj.get("x_mitre_detection", "")

        tactics: list[str] = [
            phase["phase_name"]
            for phase in obj.get("kill_chain_phases", [])
            if phase.get("kill_chain_name") == "mitre-attack"
        ]

        raw_mitigations = technique_mitigations.get(obj["id"], [])
        mitigation_pairs: list[tuple[str, str]] = [
            (m.get("name", ""), m.get("description", ""))
            for m in raw_mitigations
        ]

        # Extract date prefix (STIX 'modified' is e.g. "2023-10-04T12:34:56.789Z")
        modified: str | None = obj.get("modified")
        date = modified[:10] if modified else None

        section = tactics[0] if tactics else ""

        text = _build_text(name, technique_id, tactics, description, mitigation_pairs, detection)

        docs.append(
            Document(
                doc_id=f"mitre-{technique_id}",
                title=f"{name} ({technique_id})",
                source="mitre",
                section=section,
                date=date,
                url=_attck_url(technique_id),
                text=text,
            )
        )

    return docs
