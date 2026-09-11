# 🔒 VYOMNETRA Cybersecurity & Data Integrity Policy

VYOMNETRA implements defense-in-depth cybersecurity mechanisms to protect orbital tracking intelligence and ensure operational compliance.

---

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in VYOMNETRA:
1. **Do NOT** open a public issue.
2. Submit a security advisory privately via GitHub Security Advisories or contact the repository maintainer.
3. Include reproducible test steps, affected endpoints, and sample payloads.

Reports will be acknowledged within 48 hours and investigated promptly.

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
