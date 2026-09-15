"""Evidence Binder — hash chain integrity for data provenance.

Each piece of evidence in the ontology can be linked via a hash chain,
ensuring that report data, recommendations, and QA results are traceable
back to their source snapshots and cannot be silently modified.
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("gw2.ontology.evidence")


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_content(data: Any) -> str:
    """SHA-256 hash of arbitrary data (stable JSON serialization)."""
    raw = json.dumps(data, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def create_chain_link(
    evidence_id: str,
    source_id: str,
    content: Any,
    previous_hash: str = "",
) -> dict:
    """Create a single link in the evidence hash chain.

    Args:
        evidence_id: Unique ID for this evidence item
        source_id:   Source object ID (e.g., snapshot, report)
        content:     The evidence content (dict, list, etc.)
        previous_hash: Hash of the previous link in the chain (empty for root)

    Returns:
        dict with link_id, source_id, content_hash, previous_hash,
        chain_hash (combined hash including previous), timestamp
    """
    content_hash = hash_content(content)
    chain_input = f"{previous_hash}|{evidence_id}|{content_hash}"
    chain_hash = hashlib.sha256(chain_input.encode("utf-8")).hexdigest()

    return {
        "link_id": evidence_id,
        "source_id": source_id,
        "content_hash": content_hash,
        "previous_hash": previous_hash,
        "chain_hash": chain_hash,
        "timestamp": _ts(),
    }


def verify_chain(links: list[dict]) -> dict:
    """Verify the integrity of a hash chain.

    Args:
        links: Ordered list of chain link dicts (as returned by create_chain_link)

    Returns:
        dict with valid (bool), broken_at (index or -1), and details
    """
    if not links:
        return {"valid": True, "broken_at": -1, "detail": "Empty chain"}

    for i, link in enumerate(links):
        expected_prev = links[i - 1]["chain_hash"] if i > 0 else ""
        if link.get("previous_hash", "") != expected_prev:
            return {
                "valid": False,
                "broken_at": i,
                "detail": f"Link {i}: previous_hash mismatch. Expected {expected_prev[:16]}..., got {link.get('previous_hash', '')[:16]}...",
            }
        content_hash = link.get("content_hash", "")
        chain_input = f"{expected_prev}|{link['link_id']}|{content_hash}"
        expected_chain = hashlib.sha256(chain_input.encode("utf-8")).hexdigest()
        if link.get("chain_hash", "") != expected_chain:
            return {
                "valid": False,
                "broken_at": i,
                "detail": f"Link {i}: chain_hash mismatch. Chain integrity violated.",
            }

    return {
        "valid": True,
        "broken_at": -1,
        "detail": f"Chain intact: {len(links)} links verified",
    }


def build_report_chain(report_data: dict, evidence_list: list[dict]) -> list[dict]:
    """Build a full evidence chain for a report.

    Chain structure:
      report_meta (root) -> snapshot -> evidence[0] -> ... -> evidence[n] -> qa_result
    """
    links: list[dict] = []
    prev_hash = ""

    meta_link = create_chain_link(
        evidence_id=f"report_meta_{report_data.get('report_id', 0)}",
        source_id="report_generator",
        content={"report_type": report_data.get("report_type"), "access_level": report_data.get("access_level")},
        previous_hash=prev_hash,
    )
    links.append(meta_link)
    prev_hash = meta_link["chain_hash"]

    if report_data.get("snapshot_time"):
        snap_link = create_chain_link(
            evidence_id=f"snapshot_{report_data.get('report_id', 0)}",
            source_id="account_snapshot",
            content={"snapshot_time": report_data["snapshot_time"]},
            previous_hash=prev_hash,
        )
        links.append(snap_link)
        prev_hash = snap_link["chain_hash"]

    for i, ev in enumerate(evidence_list):
        ev_link = create_chain_link(
            evidence_id=ev.get("object_id", f"evidence_{i}"),
            source_id=ev.get("source_object_id", ""),
            content={"evidence_type": ev.get("evidence_type"), "text": ev.get("text", "")},
            previous_hash=prev_hash,
        )
        links.append(ev_link)
        prev_hash = ev_link["chain_hash"]

    return links
