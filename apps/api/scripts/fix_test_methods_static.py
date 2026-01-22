#!/usr/bin/env python3
"""
Fix test class methods to use @staticmethod
This resolves pytest fixture injection issues with async fixtures in class methods
"""

import re
from pathlib import Path


def fix_test_method_signatures(file_path: Path) -> int:
    """
    Remove 'self' parameter from test methods and add @staticmethod decorator

    This fixes the issue where pytest async fixtures don't inject properly
    into class instance methods with 'self' parameter.
    """
    content = file_path.read_text()
    changes = 0

    # Pattern to match test methods with self parameter
    # Matches:
    #   async def test_something(
    #       self,
    #       client: AsyncClient
    #   ):

    # Replace pattern: find async def test_* with self parameter
    # Add @staticmethod before the method if not already present
    # Remove self parameter

    lines = content.split("\n")
    new_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check if this is a test method definition
        if re.match(r"\s*async def test_\w+\(", line):
            # Check if next line has 'self' parameter
            if i + 1 < len(lines) and "self," in lines[i + 1]:
                # Check if @staticmethod is already present
                has_staticmethod = False
                j = i - 1
                while j >= 0 and (lines[j].strip().startswith("@") or not lines[j].strip()):
                    if "@staticmethod" in lines[j]:
                        has_staticmethod = True
                        break
                    if lines[j].strip() and not lines[j].strip().startswith("@"):
                        break
                    j -= 1

                # Add @staticmethod if not present
                if not has_staticmethod:
                    # Find the indentation of the async def line
                    indent = len(line) - len(line.lstrip())
                    staticmethod_line = " " * indent + "@staticmethod"

                    # Insert @staticmethod before decorators
                    # Find the first decorator line
                    insert_pos = i
                    while insert_pos > 0:
                        prev_line = lines[insert_pos - 1]
                        if prev_line.strip().startswith("@"):
                            insert_pos -= 1
                        else:
                            break

                    new_lines.insert(len(new_lines) - (i - insert_pos), staticmethod_line)
                    changes += 1

                # Remove self parameter line
                new_lines.append(line)
                i += 1
                # Skip the 'self,' line
                i += 1
                changes += 1
                continue

        new_lines.append(line)
        i += 1

    if changes > 0:
        file_path.write_text("\n".join(new_lines))
        print(f"  ✅ Fixed {changes // 2} test methods in {file_path.name}")
    else:
        print(f"  ℹ️  No changes needed in {file_path.name}")

    return changes


def main():
    test_files = [
        Path(
            "/Users/aldoruizluna/labspace/janua/apps/api/tests/integration/test_auth_registration.py"
        ),
        Path("/Users/aldoruizluna/labspace/janua/apps/api/tests/integration/test_auth_login.py"),
        Path("/Users/aldoruizluna/labspace/janua/apps/api/tests/integration/test_tokens.py"),
        Path("/Users/aldoruizluna/labspace/janua/apps/api/tests/integration/test_mfa.py"),
    ]

    print("🔧 Converting test class methods to @staticmethod")
    print("=" * 60)

    total = 0
    for file_path in test_files:
        if file_path.exists():
            total += fix_test_method_signatures(file_path)

    print("=" * 60)
    print(f"✅ Fixed {total // 2} test methods total")
    print("\nThis resolves pytest fixture injection issues with async fixtures.")
    return 0


if __name__ == "__main__":
    exit(main())
