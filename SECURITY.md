# 🔒 VYOMNETRA Cybersecurity & Data Integrity Policy

VYOMNETRA implements defense-in-depth cybersecurity mechanisms to protect orbital tracking intelligence and ensure operational compliance.

---

## 1. Cryptographic HMAC Data Signatures
- All analytical payload exports and audit log entries generate an HMAC-SHA256 signature using a secret server key (`VYOMNETRA_HMAC_SECRET`).
- Verification fails if any field, TLE parameter, or threat score is altered in transit.

## 2. Security Classification & Clearance Enforcement
- Objects and orbital records are tagged with strict security levels: `UNCLASSIFIED`, `RESTRICTED`, `CONFIDENTIAL`, `SECRET`, `TOP_SECRET`.
- The `SecurityPipelineManager` filters query results dynamically based on user identity clearance.

## 3. SQL Injection Prevention
- All database queries use parameterized SQL execution (`?` placeholders). Direct string interpolation in SQL statements is strictly forbidden.

## 4. SQLite Immutable Audit Compliance
- Conjunction alerts and data fetch records are stored with parent foreign key linkages (`PRAGMA foreign_keys = ON`).
- Orphan record detection runs continuously to verify zero untracked database modifications.
