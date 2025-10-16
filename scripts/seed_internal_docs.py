#!/usr/bin/env python3
"""
Seed internal example documents into the configured Elastic index.

Usage:
    python scripts/seed_internal_docs.py
    python scripts/seed_internal_docs.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv


def load_settings() -> Dict[str, str]:
    """Load Elastic configuration from environment variables and validate them."""
    load_dotenv()

    settings = {
        "url": os.getenv("ELASTIC_URL"),
        "index": os.getenv("ELASTIC_INDEX", "internal-docs"),
        "api_key": os.getenv("ELASTIC_API_KEY"),
    }

    missing = [name for name, value in settings.items() if not value]
    if missing:
        missing_vars = ", ".join(missing)
        raise RuntimeError(f"Missing required environment variables: {missing_vars}")

    # Strip trailing slashes so we can safely append path segments.
    settings["url"] = settings["url"].rstrip("/")
    return settings


def build_documents() -> List[Dict[str, Any]]:
    """Create a curated set of internal example documents covering multiple industries."""
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    return [
        {
            "doc_id": "AZ-MFG-2024-PLANT-GOV",
            "title": "Plant Floor Vendor Qualification Playbook",
            "industry": "manufacturing",
            "summary": "Baseline controls for approving contract manufacturers within Azion operations.",
            "internal_standards": [
                "AZ-MFG-001: Production Line Quality Assurance",
                "AZ-SEC-012: Supplier Remote Access Guardrail",
            ],
            "regulatory_references": ["ISO 9001:2015", "IATF 16949"],
            "risk_rating": "medium",
            "tags": ["supplier", "quality", "third-party"],
            "last_reviewed": "2024-05-01",
            "author_team": "Manufacturing Governance",
            "body": (
                "Per AZ-MFG-001 and AZ-SEC-012, every contract manufacturer must document "
                "preventive maintenance schedules, secure remote access gateways, and batch "
                "traceability checkpoints aligned to ISO 9001 and IATF 16949 requirements."
            ),
            "ingested_at": now,
        },
        {
            "doc_id": "AZ-SWE-2024-SDLC",
            "title": "Secure SDLC Checklist for Platform Services",
            "industry": "technology",
            "summary": "Mandatory secure development lifecycle controls for cloud-native services.",
            "internal_standards": [
                "AZ-SWE-008: Secure Development Lifecycle",
                "AZ-SEC-021: Secrets Management Standard",
            ],
            "regulatory_references": ["SOC 2", "ISO 27001"],
            "risk_rating": "high",
            "tags": ["engineering", "security", "release"],
            "last_reviewed": "2024-04-18",
            "author_team": "Platform Security",
            "body": (
                "Engineering squads must evidence code review gates, threat modeling outputs, "
                "and dependency scanning attestation forms as defined in AZ-SWE-008. "
                "Service credentials are rotated using the AZ-SEC-021 secret broker policy "
                "before each production deploy."
            ),
            "ingested_at": now,
        },
        {
            "doc_id": "AZ-SLS-2024-DATA-HANDLING",
            "title": "Revenue Operations CRM Data Handling Guide",
            "industry": "sales",
            "summary": "Controls for safeguarding prospect data inside Azion's revenue platforms.",
            "internal_standards": [
                "AZ-SLS-010: Commercial Data Minimization",
                "AZ-PRIV-004: Customer Contact Consent Standard",
            ],
            "regulatory_references": ["GDPR", "CCPA"],
            "risk_rating": "medium",
            "tags": ["crm", "privacy", "go-to-market"],
            "last_reviewed": "2024-03-12",
            "author_team": "Revenue Operations",
            "body": (
                "Opportunity notes must only include data fields enumerated in AZ-SLS-010. "
                "Any enrichment workflow invoking third parties requires the consent records "
                "captured per AZ-PRIV-004 and must purge expired opt-ins within 14 days."
            ),
            "ingested_at": now,
        },
        {
            "doc_id": "AZ-HLTH-2024-TELEHEALTH",
            "title": "Telehealth Protected Health Information Guardrail",
            "industry": "healthcare",
            "summary": "Safeguards for processing clinical data transmitted through Azion telehealth integrations.",
            "internal_standards": [
                "AZ-HLTH-014: PHI Encryption and Masking Policy",
                "AZ-SEC-019: Clinical Access Monitoring",
            ],
            "regulatory_references": ["HIPAA", "HITECH"],
            "risk_rating": "high",
            "tags": ["phi", "encryption", "audit"],
            "last_reviewed": "2024-02-27",
            "author_team": "Clinical Compliance",
            "body": (
                "Endpoints processing PHI implement envelope encryption dictated by AZ-HLTH-014 "
                "with FIPS 140-2 validated modules. Session logs are streamed into the "
                "continuous monitoring tier described in AZ-SEC-019 for 90-day retention."
            ),
            "ingested_at": now,
        },
        {
            "doc_id": "AZ-CYBER-2024-IR-PLAYBOOK",
            "title": "Cyber Defense Incident Response Matrix",
            "industry": "cybersecurity",
            "summary": "Escalation matrix and containment tactics for security operations center analysts.",
            "internal_standards": [
                "AZ-CYBER-003: Incident Severity Classification",
                "AZ-SEC-030: Endpoint Isolation Standard",
            ],
            "regulatory_references": ["NIST CSF", "CIS Controls v8"],
            "risk_rating": "critical",
            "tags": ["soc", "incident-response", "playbook"],
            "last_reviewed": "2024-05-07",
            "author_team": "Security Operations",
            "body": (
                "SOC leads triage alerts using the AZ-CYBER-003 severity taxonomy and deploy "
                "isolation actions through the AZ-SEC-030 orchestration runbooks. Each major "
                "incident requires post-action review with documented CFR alignment."
            ),
            "ingested_at": now,
        },
        {
            "doc_id": "AZ-GOV-2024-PROCUREMENT",
            "title": "Public Sector Procurement Assurance Checklist",
            "industry": "government",
            "summary": "Assessment controls for onboarding federal and state procurement projects.",
            "internal_standards": [
                "AZ-GOV-002: Public Sector Engagement Standard",
                "AZ-RISK-011: Export Control Review Process",
            ],
            "regulatory_references": ["FedRAMP Moderate", "ITAR"],
            "risk_rating": "high",
            "tags": ["public-sector", "procurement", "compliance"],
            "last_reviewed": "2024-01-30",
            "author_team": "Public Sector Programs",
            "body": (
                "Project intake must evidence completion of the AZ-GOV-002 control pack, "
                "including FedRAMP boundary diagrams and contractor clearance attestations. "
                "Any cross-border data flow is routed through the AZ-RISK-011 export review."
            ),
            "ingested_at": now,
        },
        {
            "doc_id": "AZ-LAW-2024-DIGITAL-EVIDENCE",
            "title": "Digital Evidence Chain-of-Custody Blueprint",
            "industry": "law enforcement",
            "summary": "Guidelines for hosting justice sector workloads and preserving digital evidence.",
            "internal_standards": [
                "AZ-LAW-004: Justice Systems Data Retention Standard",
                "AZ-SEC-027: Evidence Vault Access Control",
            ],
            "regulatory_references": ["CJIS", "NIST 800-53"],
            "risk_rating": "critical",
            "tags": ["chain-of-custody", "logging", "identity"],
            "last_reviewed": "2024-03-05",
            "author_team": "Public Safety Programs",
            "body": (
                "Evidence uploads are tagged with immutable ledger references per AZ-LAW-004 "
                "and require multifactor approvals aligned to AZ-SEC-027. Automated alerts "
                "benchmark retention timers against CJIS reporting obligations."
            ),
            "ingested_at": now,
        },
        {
            "doc_id": "AZ-AGR-2024-IOT-TELEMETRY",
            "title": "Agricultural IoT Telemetry Governance Pack",
            "industry": "agriculture",
            "summary": "Operational safeguards for smart farming deployments leveraging Azion edge gateways.",
            "internal_standards": [
                "AZ-AGR-006: Field Sensor Data Integrity",
                "AZ-SEC-025: Edge Device Hardening Baseline",
            ],
            "regulatory_references": ["USDA Smart Agriculture Guidelines"],
            "risk_rating": "medium",
            "tags": ["iot", "edge", "telemetry"],
            "last_reviewed": "2024-02-09",
            "author_team": "Edge Solutions",
            "body": (
                "Telemetry packets are validated against the CRC controls in AZ-AGR-006 to "
                "prevent drift in irrigation planning. Gateways must boot with secure elements "
                "configured under AZ-SEC-025 and report posture to the agronomy console hourly."
            ),
            "ingested_at": now,
        },
        {
            "doc_id": "AZ-FIN-2024-LIQUIDITY-RISK",
            "title": "Treasury Liquidity Stress Testing Protocol",
            "industry": "financial services",
            "summary": "Stress testing cadence for treasury operations handling enterprise liquidity pools.",
            "internal_standards": [
                "AZ-FIN-009: Liquidity Risk Governance",
                "AZ-RISK-015: Model Validation Standard",
            ],
            "regulatory_references": ["Basel III", "FFIEC"],
            "risk_rating": "high",
            "tags": ["treasury", "risk", "analytics"],
            "last_reviewed": "2024-04-02",
            "author_team": "Corporate Treasury",
            "body": (
                "Scenario libraries documented in AZ-FIN-009 must be refreshed quarterly with "
                "new macroeconomic triggers. Quantitative models require annual independent "
                "validation per AZ-RISK-015 prior to presentation to the Risk Committee."
            ),
            "ingested_at": now,
        },
        {
            "doc_id": "AZ-ENE-2024-GRID-RESILIENCE",
            "title": "Grid Edge Resilience Architecture Standard",
            "industry": "energy",
            "summary": "Reliability requirements for energy sector workloads deployed on Azion edge nodes.",
            "internal_standards": [
                "AZ-ENE-003: Critical Infrastructure Continuity",
                "AZ-SEC-028: Operational Technology Segmentation",
            ],
            "regulatory_references": ["NERC CIP", "DOE C2M2"],
            "risk_rating": "critical",
            "tags": ["energy", "resilience", "ot-security"],
            "last_reviewed": "2024-05-10",
            "author_team": "Critical Infrastructure Team",
            "body": (
                "Regional failover must conform to AZ-ENE-003 dual-operator readiness drills "
                "and validate OT segmentation handoffs prescribed in AZ-SEC-028. Resilience "
                "metrics are logged for DOE C2M2 scorecard submissions."
            ),
            "ingested_at": now,
        },
    ]


def build_bulk_payload(documents: List[Dict[str, Any]]) -> str:
    """Convert documents into the newline-delimited JSON bulk payload."""
    lines = []
    for doc in documents:
        lines.append(json.dumps({"index": {}}))
        lines.append(json.dumps(doc))
    return "\n".join(lines) + "\n"


def ingest_documents(*, url: str, index: str, api_key: str, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Send the documents to Elastic using the Bulk API and return the parsed response."""
    endpoint = f"{url}/{index}/_bulk"
    payload = build_bulk_payload(documents)

    response = requests.post(
        endpoint,
        data=payload,
        headers={
            "Authorization": f"ApiKey {api_key}",
            "Content-Type": "application/x-ndjson",
        },
        params={"refresh": "wait_for"},
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()
    if data.get("errors"):
        raise RuntimeError(f"Bulk ingest reported errors: {json.dumps(data, indent=2)}")
    return data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed internal documents into Elastic.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the documents without sending them to Elastic.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_settings()
    documents = build_documents()

    if args.dry_run:
        print(json.dumps(documents, indent=2))
        print(f"\nPrepared {len(documents)} documents for index '{settings['index']}'.")
        return

    result = ingest_documents(
        url=settings["url"],
        index=settings["index"],
        api_key=settings["api_key"],
        documents=documents,
    )

    item_count = len(result.get("items", []))
    print(f"Ingested {item_count} documents into index '{settings['index']}'.")


if __name__ == "__main__":
    main()
