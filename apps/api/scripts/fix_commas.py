#!/usr/bin/env python3
"""
Fix missing commas in test function parameters
"""

import re
from pathlib import Path


def fix_missing_commas(file_path: Path) -> int:
    """Fix missing commas after 'client: AsyncClient' lines"""
    content = file_path.read_text()

    # Pattern: 'client: AsyncClient' at end of line followed by another parameter
    # Replace with: 'client: AsyncClient,'
    pattern = r"(\s+client: AsyncClient)\n(\s+\w+:)"
    replacement = r"\1,\n\2"

    new_content, count = re.subn(pattern, replacement, content)

    if count > 0:
        file_path.write_text(new_content)
        print(f"  ✅ Fixed {count} missing commas in {file_path.name}")
    else:
        print(f"  ℹ️  No missing commas in {file_path.name}")

    return count


def main():
    test_files = [
        Path(
            "/Users/aldoruizluna/labspace/janua/apps/api/tests/integration/test_auth_registration.py"
        ),
        Path(
            "/Users/aldoruizluna/labspace/janua/apps/api/tests/integration/test_auth_login_complete.py"
        ),
        Path("/Users/aldoruizluna/labspace/janua/apps/api/tests/integration/test_tokens.py"),
        Path("/Users/aldoruizluna/labspace/janua/apps/api/tests/integration/test_mfa.py"),
    ]

    print("🔧 Fixing missing commas in test parameters")
    print("=" * 60)

    total = 0
    for file_path in test_files:
        if file_path.exists():
            total += fix_missing_commas(file_path)

    print("=" * 60)
    print(f"✅ Fixed {total} missing commas total")
    return 0


if __name__ == "__main__":
    exit(main())
