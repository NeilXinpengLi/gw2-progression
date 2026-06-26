"""Report Mapper — maps generated reports to ontology evidence objects.

Every paid report must have traceable evidence: which snapshot, which goals,
which builds, which market signals contributed to each recommendation.
"""

import logging
from typing import Any

from . import object_store as store
from .models import OntologyObject, QAReport

logger = logging.getLogger("gw2.ontology.report")

PUBLICATION_REQUIREMENTS = [
    "snapshot_exists",
    "snapshot_freshness_ok",
    "no_api_key_leak",
    "evidence_cited",
]


async def map_report_to_evidence(
    report_data: dict,
    account_name: str,
    qa_report: QAReport | None = None,
) -> list[OntologyObject]:
    created: list[OntologyObject] = []

    report_obj = store.register_object(
        class_name="report",
        account_name=account_name,
        properties={
            "report_id": report_data.get("report_id", 0),
            "report_type": report_data.get("report_type", "free"),
            "title": report_data.get("title", ""),
            "access_level": report_data.get("access_level", "private"),
            "snapshot_time": report_data.get("snapshot_time", ""),
            "recommendation_count": len(report_data.get("recommendations", [])),
            "qa_status": qa_report.status if qa_report else "unchecked",
        },
        privacy_scope=report_data.get("access_level", "private"),
    )
    created.append(report_obj)

    snapshot_objs = store.get_objects_by_account("account_snapshot", account_name)
    if snapshot_objs:
        latest = max(snapshot_objs, key=lambda o: o.created_at)
        store.register_relation(
            source_id=report_obj.object_id,
            target_id=latest.object_id,
            relation_type="generated_from",
            confidence=0.95,
        )

    for i, rec in enumerate(report_data.get("recommendations", [])):
        evidence_obj = store.register_object(
            class_name="evidence",
            account_name=account_name,
            properties={
                "evidence_type": "recommendation",
                "source": "report_generator",
                "text": rec if isinstance(rec, str) else str(rec),
                "index": i,
                "report_id": report_data.get("report_id", 0),
            },
            privacy_scope="shared",
            source_object_id=report_obj.object_id,
        )
        created.append(evidence_obj)
        store.register_relation(
            source_id=evidence_obj.object_id,
            target_id=report_obj.object_id,
            relation_type="validates",
            confidence=0.90,
        )

    if qa_report:
        qa_props = {
            "target_id": qa_report.target_object_id,
            "status": qa_report.status,
            "passed": qa_report.passed,
            "failed": qa_report.failed,
            "blocking_errors": qa_report.blocking_errors,
            "warnings": qa_report.warnings,
        }
        qa_obj = store.register_object(
            class_name="evidence",
            account_name=account_name,
            properties={
                "evidence_type": "qa_report",
                "source": "qa_gate",
                "qa_result": qa_props,
            },
            privacy_scope="private",
            source_object_id=report_obj.object_id,
        )
        created.append(qa_obj)
        store.register_relation(
            source_id=qa_obj.object_id,
            target_id=report_obj.object_id,
            relation_type="validates",
            confidence=1.0,
        )

    return created


def check_publication_requirements(
    report_data: dict,
    qa_report: QAReport | None = None,
) -> dict[str, Any]:
    result = {
        "publishable": False,
        "missing_requirements": [],
        "blocking_issues": [],
        "warnings": [],
    }

    if qa_report is None:
        result["missing_requirements"].append("qa_report")
        result["blocking_issues"].append("QA report is required before publication.")
        return result

    if qa_report.status != "pass":
        result["blocking_issues"].extend(qa_report.blocking_errors)
        result["warnings"].extend(qa_report.warnings)
        return result

    access_level = report_data.get("access_level", "private")
    if access_level == "public":
        snapshot_time = report_data.get("snapshot_time", "")
        if not snapshot_time:
            result["missing_requirements"].append("snapshot_time")
            result["blocking_issues"].append("Public reports require a snapshot timestamp.")

    result["publishable"] = len(result["blocking_issues"]) == 0
    return result
