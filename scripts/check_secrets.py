#!/usr/bin/env python3
"""Static Security Secret Scanner.

Scans the codebase for hardcoded passwords, tokens, API keys, and private keys.
"""

import sys
import re
from pathlib import Path

SECRET_PATTERNS = [
    (re.compile(r'(?i)(api_key|apikey|secret_key|private_key|token|password)\s*=\s*["\'][A-Za-z0-9_\-]{16,}["\']'), "Hardcoded Secret / API Key Token"),
    (re.compile(r'-----BEGIN PRIVATE KEY-----'), "PEM Private Key Block"),
    (re.compile(r'-----BEGIN RSA PRIVATE KEY-----'), "RSA Private Key Block"),
]

EXCLUDE_DIRS = {".venv", ".git", "__pycache__", "build", "dist", "node_modules", ".pytest_cache"}
EXCLUDE_FILES = {"DECISIONS.md", "check_secrets.py"}


def scan_secrets(root_dir: Path) -> int:
    """Scans all source files in directory for forbidden secret patterns."""
    violations = 0

    for path in root_dir.rglob("*"):
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        if path.name in EXCLUDE_FILES or not path.is_file():
            continue
        if path.suffix not in (".py", ".json", ".yaml", ".yml", ".env", ".toml", ".sh"):
            continue

        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            for pattern, msg in SECRET_PATTERNS:
                matches = pattern.findall(content)
                if matches:
                    print(f"SECURITY VIOLATION in {path.relative_to(root_dir)}: {msg} (found {len(matches)} matches)")
                    violations += 1
        except Exception:
            pass

    return violations


if __name__ == "__main__":
    workspace_root = Path(__file__).parent.parent
    v_count = scan_secrets(workspace_root)
    if v_count > 0:
        print(f"\nScan completed: {v_count} security secret violations found!")
        sys.exit(1)
    else:
        print("Scan completed: 0 secret violations found. Repository clean.")
        sys.exit(0)
