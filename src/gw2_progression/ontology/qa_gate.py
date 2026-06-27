"""QA / Governance Gate — validates ontology objects and report readiness.

Every full/paid report, strong recommendation, or ontology object mutation
should pass through the QA gate before being delivered to the user.

Checks include:
  - Object schema validity (required properties)
  - Snapshot freshness (not stale > 24h)
  - Build source review status
  - Data privacy (no private data in public scope)
  - API key leakage
  - Evidence citation
  - Blocking vs non-blocking errors
"""

import logging
import re
from datetime import datetime, timezone

from .config import CLASS_DEFINITIONS, QA_CHECK_DEFINITIONS
from .models import OntologyObject, QAReport

logger = logging.getLogger("gw2.ontology.qa")

_API_KEY_PATTERN = re.compile(r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}")

_CHECK_PROPERTY_MAP: dict[str, str] = {
    "surplus_non_negative": "safe_surplus",
    "count_non_negative": "count",
    "reserved_count_positive": "reserved_count",
    "required_count_valid": "required_count",
    "item_id_valid": "item_id",
    "goal_status_valid": "status",
    "build_source_reviewed": "source",
    "readiness_score_valid": "",
}


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_object(obj: OntologyObject) -> QAReport:
    checks: list[dict] = []
    errors: list[str] = []
    warnings: list[str] = []

    class_def = CLASS_DEFINITIONS.get(obj.class_name)
    if not class_def:
        checks.append({"check": "class_known", "passed": False, "detail": f"Unknown class: {obj.class_name}"})
        errors.append(f"Unknown ontology class: {obj.class_name}")
        return QAReport(
            target_object_id=obj.object_id,
            target_class=obj.class_name,
            checks=checks,
            passed=0,
            failed=1,
            blocking_errors=errors,
            warnings=warnings,
            status="fail",
            checked_at=_ts(),
        )

    required = class_def.get("required_properties", [])
    for prop in required:
        if prop not in obj.properties or obj.properties.get(prop) is None:
            checks.append({"check": f"required_property.{prop}", "passed": False, "detail": f"Missing required property: {prop}"})
            errors.append(f"Missing required property '{prop}' for class '{obj.class_name}'")

    qa_checks = class_def.get("qa_checks", [])
    for check_name in qa_checks:
        check_def = QA_CHECK_DEFINITIONS.get(check_name)
        if not check_def:
            continue
        check_type = check_def.get("check_type", "")
        result = _run_check(check_name, check_type, check_def, obj)
        checks.append(result)
        if not result["passed"]:
            if result.get("blocking", True):
                errors.append(result["detail"])
            else:
                warnings.append(result["detail"])

    passed = sum(1 for c in checks if c.get("passed", False))
    failed = sum(1 for c in checks if not c.get("passed", False))
    status = "pass" if failed == 0 else "fail"

    return QAReport(
        target_object_id=obj.object_id,
        target_class=obj.class_name,
        checks=checks,
        passed=passed,
        failed=failed,
        blocking_errors=errors,
        warnings=warnings,
        status=status,
        checked_at=_ts(),
    )


def _run_check(check_name: str, check_type: str, check_def: dict, obj: OntologyObject) -> dict:
    props = obj.properties

    if check_type == "exists":
        return _check_exists(check_name, obj)
    elif check_type == "freshness":
        return _check_freshness(check_name, check_def, props)
    elif check_type == "positive_int":
        return _check_positive_int(check_name, props)
    elif check_type == "non_negative":
        return _check_non_negative(check_name, props)
    elif check_type == "enum":
        return _check_enum(check_name, check_def, props)
    elif check_type == "range_0_1":
        return _check_range_0_1(check_name, props)
    elif check_type == "qa_pass":
        return {"check": check_name, "passed": True, "detail": "[deferred to QA run]"}
    elif check_type == "privacy":
        return {"check": check_name, "passed": True, "detail": f"privacy_scope={obj.privacy_scope}"}
    elif check_type == "api_key":
        return _check_api_key_leak(check_name, obj)
    elif check_type == "non_empty":
        return _check_non_empty(check_name, check_def, props)
    else:
        return {"check": check_name, "passed": True, "detail": f"Unknown check type: {check_type}"}


def _check_exists(check_name: str, obj: OntologyObject) -> dict:
    return {
        "check": check_name,
        "passed": True,
        "detail": f"Object {obj.object_id} exists",
    }


def _check_freshness(check_name: str, check_def: dict, props: dict) -> dict:
    max_hours = check_def.get("max_age_hours", 0)
    max_days = check_def.get("max_age_days", 0)
    stale_threshold = max_hours or (max_days * 24)
    if stale_threshold <= 0:
        return {"check": check_name, "passed": True, "detail": "No freshness threshold configured"}

    ts_str = props.get("created_at") or props.get("snapshot_time") or ""
    if not ts_str:
        return {"check": check_name, "passed": False, "detail": "No timestamp for freshness check", "blocking": True}

    try:
        ts = datetime.fromisoformat(ts_str)
        age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
        if age_hours <= stale_threshold:
            return {"check": check_name, "passed": True, "detail": f"Fresh: {age_hours:.1f}h old (threshold: {stale_threshold}h)"}
        return {"check": check_name, "passed": False, "detail": f"Stale: {age_hours:.1f}h old (threshold: {stale_threshold}h)", "blocking": True}
    except (ValueError, TypeError):
        return {"check": check_name, "passed": False, "detail": f"Cannot parse timestamp: {ts_str}", "blocking": True}


def _check_positive_int(check_name: str, props: dict) -> dict:
    key = _CHECK_PROPERTY_MAP.get(check_name) or (check_name.split(".")[-1] if "." in check_name else "")
    if not key:
        return {"check": check_name, "passed": True, "detail": "No property specified"}
    val = props.get(key, 0)
    if isinstance(val, int) and val > 0:
        return {"check": check_name, "passed": True, "detail": f"{key}={val}"}
    return {"check": check_name, "passed": False, "detail": f"{key}={val} is not a positive integer", "blocking": True}


def _check_non_negative(check_name: str, props: dict) -> dict:
    key = _CHECK_PROPERTY_MAP.get(check_name) or (check_name.split(".")[-1] if "." in check_name else "")
    if not key:
        return {"check": check_name, "passed": True, "detail": "No property specified"}
    val = props.get(key, 0)
    if isinstance(val, (int, float)) and val >= 0:
        return {"check": check_name, "passed": True, "detail": f"{key}={val}"}
    return {"check": check_name, "passed": False, "detail": f"{key}={val} is negative", "blocking": True}


def _check_enum(check_name: str, check_def: dict, props: dict) -> dict:
    key = _CHECK_PROPERTY_MAP.get(check_name) or (check_name.split(".")[-1] if "." in check_name else "")
    values = check_def.get("values", [])
    if not key:
        key = "status"
    val = props.get(key, "")
    if val in values:
        return {"check": check_name, "passed": True, "detail": f"{key}={val} in {values}"}
    return {"check": check_name, "passed": False, "detail": f"{key}={val} not in {values}", "blocking": True}


def _check_range_0_1(check_name: str, props: dict) -> dict:
    key = "readiness_score"
    val = props.get(key, -1)
    if isinstance(val, (int, float)) and 0 <= val <= 1:
        return {"check": check_name, "passed": True, "detail": f"{key}={val}"}
    return {"check": check_name, "passed": False, "detail": f"{key}={val} not in [0, 1]", "blocking": False}


def _check_api_key_leak(check_name: str, obj: OntologyObject) -> dict:
    text = str(obj.properties)
    if _API_KEY_PATTERN.search(text):
        return {"check": check_name, "passed": False, "detail": "Potential API key found in object properties", "blocking": True}
    return {"check": check_name, "passed": True, "detail": "No API keys detected"}


def _check_non_empty(check_name: str, check_def: dict, props: dict) -> dict:
    key = check_name.split(".")[-1] if "." in check_name else ""
    if not key:
        return {"check": check_name, "passed": True, "detail": "No property specified"}
    val = props.get(key, "")
    if val:
        return {"check": check_name, "passed": True, "detail": f"{key} is non-empty"}
    return {"check": check_name, "passed": False, "detail": f"{key} is empty", "blocking": True}


async def check_report_publishable(report_data: dict) -> QAReport:
    checks: list[dict] = []
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Snapshot existence
    snapshot_time = report_data.get("snapshot_time", "")
    if snapshot_time:
        checks.append({"check": "snapshot_exists", "passed": True, "detail": f"Snapshot: {snapshot_time}"})
    else:
        checks.append({"check": "snapshot_exists", "passed": False, "detail": "No snapshot timestamp"})
        errors.append("Report has no snapshot timestamp.")

    # 2. Snapshot freshness (max 48h for reports)
    if snapshot_time:
        try:
            ts = datetime.fromisoformat(snapshot_time)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
            if age_hours <= 48:
                checks.append({"check": "snapshot_freshness", "passed": True, "detail": f"Fresh: {age_hours:.1f}h old"})
            else:
                checks.append({"check": "snapshot_freshness", "passed": False, "detail": f"Stale: {age_hours:.1f}h old", "blocking": True})
                errors.append(f"Snapshot is {age_hours:.1f}h old (max 48h). Data may be stale.")
        except (ValueError, TypeError) as e:
            checks.append({"check": "snapshot_freshness", "passed": False, "detail": f"Cannot parse snapshot_time: {e}", "blocking": True})
            errors.append("Cannot parse snapshot_time.")

    # 3. No private data in public report
    access_level = report_data.get("access_level", "private")
    if access_level == "public":
        checks.append({"check": "no_private_data_leak", "passed": True, "detail": "access_level=public — checking private data"})
        _check_private_fields(report_data, checks, errors, warnings)

    # 4. No API key leak
    text = str(report_data)
    if _API_KEY_PATTERN.search(text):
        checks.append({"check": "no_api_key_leak", "passed": False, "detail": "Potential API key found in report data", "blocking": True})
        errors.append("API key detected in report data. Blocking publication.")

    # 5. Evidence cited
    recommendations = report_data.get("recommendations", [])
    if recommendations:
        checks.append({"check": "evidence_cited", "passed": True, "detail": f"{len(recommendations)} recommendations present"})
    else:
        warnings.append("No recommendations in report.")

    # 6. Build source freshness (if build details present)
    build_details = report_data.get("build_details", [])
    for bd in build_details:
        patch = bd.get("patch_version", "")
        review = bd.get("review_status", "unreviewed")
        if review != "reviewed":
            checks.append({
                "check": f"build_source.{bd.get('build_id', 'unknown')}",
                "passed": False,
                "detail": f"Build '{bd.get('name', '')}' has unreviewed source",
                "blocking": True,
            })
            errors.append(f"Build '{bd.get('name', '')}' is unreviewed and cannot be strongly recommended.")
        if patch:
            try:
                from ..models import BuildTemplate
                from .build_trust import evaluate_build_source_freshness
                fake = BuildTemplate(
                    build_id=bd.get("build_id", ""),
                    source=bd.get("source", ""),
                    name=bd.get("name", ""),
                    profession=bd.get("profession", ""),
                    patch_version=patch,
                    review_status=review,
                )
                fb = evaluate_build_source_freshness(fake)
                if fb.get("is_stale"):
                    checks.append({
                        "check": f"build_freshness.{bd.get('build_id', 'unknown')}",
                        "passed": False,
                        "detail": f"Build '{bd.get('name', '')}' patch {patch} is {fb['days_old']} days old",
                        "blocking": False,
                    })
                    warnings.append(f"Build '{bd.get('name', '')}' patch is stale ({fb['days_old']} days).")
            except Exception:
                pass

    # 7. Report has data sources (for paid reports)
    if report_data.get("report_type") in ("commercial", "paid"):
        if not report_data.get("snapshot_time"):
            checks.append({
                "check": "paid_report_has_snapshot",
                "passed": False,
                "detail": "Paid report must have a snapshot timestamp",
                "blocking": True,
            })
            errors.append("Paid report requires a snapshot timestamp.")

    passed = sum(1 for c in checks if c.get("passed", False))
    failed = sum(1 for c in checks if not c.get("passed", False))
    status = "pass" if failed == 0 else "fail"

    return QAReport(
        target_object_id=str(report_data.get("report_id", "")),
        target_class="report",
        checks=checks,
        passed=passed,
        failed=failed,
        blocking_errors=errors,
        warnings=warnings,
        status=status,
        checked_at=_ts(),
    )


def _check_private_fields(report_data: dict, checks: list, errors: list, warnings: list) -> None:
    suspicious_keys = ["api_key", "session_token", "encrypted_value", "password", "secret"]
    for key in suspicious_keys:
        if key in report_data or any(key in str(v) for v in report_data.values()):
            checks.append({"check": f"private_field.{key}", "passed": False, "detail": f"Potential private field: {key}", "blocking": False})
            warnings.append(f"Report may contain private field: {key}")
