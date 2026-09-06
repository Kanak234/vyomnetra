"""VYOMNETRA Cybersecurity & Data Security Layer.

Provides HMAC-SHA256 data pipeline integrity verification, append-only hash-chained audit logging,
`verify_audit_chain()` validation, and tiered security classification access control (UNCLASSIFIED to TOP_SECRET).
"""

import hmac
import hashlib
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

from vyomnetra.config import settings
from vyomnetra.utils.logger import get_logger

logger = get_logger("vyomnetra.intelligence.security")

# Hierarchical security levels (5 Tiers)
CLASSIFICATION_HIERARCHY = {
    "UNCLASSIFIED": 0,
    "RESTRICTED": 1,
    "CONFIDENTIAL": 2,
    "SECRET": 3,
    "TOP_SECRET": 4
}


class AuditRecord(dict):
    """Dict subclass representing a hash-chained audit log entry."""
    pass


class SecurityPipelineManager:
    """Security manager for access control, payload encryption verification, and hash-chained audit trails."""

    def __init__(self, secret_key: str = "VYOMNETRA_ISRO_SSA_SECURE_KEY_2026"):
        self.secret_key = secret_key.encode("utf-8")
        self.audit_chain: List[Dict[str, Any]] = []

    def generate_hmac_signature(self, payload: Dict[str, Any]) -> str:
        """Generates SHA-256 HMAC signature for any data payload dictionary."""
        payload_str = json.dumps(payload, sort_keys=True)
        return hmac.new(self.secret_key, payload_str.encode("utf-8"), hashlib.sha256).hexdigest()

    def verify_hmac_signature(self, payload: Dict[str, Any], signature: str) -> bool:
        """Verifies payload integrity using HMAC-SHA256 signature."""
        expected = self.generate_hmac_signature(payload)
        return hmac.compare_digest(expected, signature)

    def filter_by_classification(
        self,
        records: List[Dict[str, Any]],
        user_clearance: str = "UNCLASSIFIED"
    ) -> List[Dict[str, Any]]:
        """Filters dataset records according to user security clearance level."""
        user_level = CLASSIFICATION_HIERARCHY.get(user_clearance.upper(), 0)

        filtered = []
        for r in records:
            item_classification = r.get("classification", "UNCLASSIFIED").upper()
            item_level = CLASSIFICATION_HIERARCHY.get(item_classification, 0)

            if item_level <= user_level:
                filtered.append(r)

        return filtered

    def append_audit_record(
        self,
        action: str,
        user_id: str,
        resource_id: str,
        status: str = "SUCCESS"
    ) -> Dict[str, Any]:
        """Appends a cryptographically hash-chained record to the audit chain."""
        now_utc = datetime.now(timezone.utc).isoformat()
        prev_hash = self.audit_chain[-1]["record_hash"] if self.audit_chain else "0000000000000000000000000000000000000000000000000000000000000000"

        record_data = {
            "timestamp": now_utc,
            "action": action,
            "user_id": user_id,
            "resource_id": resource_id,
            "status": status,
            "previous_hash": prev_hash
        }

        rec_str = json.dumps(record_data, sort_keys=True)
        rec_hash = hashlib.sha256(rec_str.encode("utf-8")).hexdigest()

        record_data["record_hash"] = rec_hash
        record_data["hmac_signature"] = self.generate_hmac_signature(record_data)

        self.audit_chain.append(record_data)
        return record_data

    def verify_audit_chain(self, chain: Optional[List[Dict[str, Any]]] = None) -> Tuple[bool, str]:
        """Verifies the SHA-256 hash chain integrity of audit records to detect tampering."""
        target_chain = chain if chain is not None else self.audit_chain
        if not target_chain:
            return True, "Audit chain is empty."

        expected_prev_hash = "0000000000000000000000000000000000000000000000000000000000000000"

        for idx, rec in enumerate(target_chain):
            if rec.get("previous_hash") != expected_prev_hash:
                return False, f"Tampering detected at record {idx}! Previous hash mismatch."

            # Verify hash
            rec_copy = {k: v for k, v in rec.items() if k not in ("record_hash", "hmac_signature")}
            rec_str = json.dumps(rec_copy, sort_keys=True)
            calc_hash = hashlib.sha256(rec_str.encode("utf-8")).hexdigest()

            if calc_hash != rec.get("record_hash"):
                return False, f"Tampering detected at record {idx}! Record hash altered."

            expected_prev_hash = rec.get("record_hash")

        return True, f"Audit chain verified successfully across {len(target_chain)} records."
