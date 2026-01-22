#!/usr/bin/env python3
"""
Convert class-based pytest tests to function-based tests
This resolves pytest async fixture injection issues
"""

import re
from pathlib import Path
from typing import Tuple


def convert_test_file(file_path: Path) -> Tuple[int, int]:
    """
    Convert class-based tests to function-based tests

    Returns:
        (classes_removed, methods_converted)
    """
    content = file_path.read_text()
    lines = content.split("\n")

    new_lines = []
    classes_removed = 0
    methods_converted = 0

    i = 0
    in_class = False

    while i < len(lines):
        line = lines[i]

        # Detect class definition
        if re.match(r"^class Test\w+:", line):
            in_class = True
            len(line) - len(line.lstrip())
            classes_removed += 1

            # Skip the class definition and its docstring
            i += 1
            # Skip docstring if present
            if i < len(lines) and '"""' in lines[i]:
                # Multi-line docstring
                while i < len(lines) and not (
                    i > 0 and '"""' in lines[i] and lines[i].strip() != '"""'
                ):
                    i += 1
                i += 1  # Skip closing """
            elif i < len(lines) and lines[i].strip().startswith('"""'):
                i += 1

            # Skip empty lines after class docstring
            while i < len(lines) and not lines[i].strip():
                i += 1

            continue

        # Convert test methods to functions
        if in_class and "@staticmethod" in line:
            # Remove @staticmethod decorator
            i += 1
            continue

        # Process test method definition
        if in_class and re.match(r"\s+@pytest\.mark\.", line):
            # Collect all decorators
            decorators = []
            method_indent = len(line) - len(line.lstrip())

            while i < len(lines) and (lines[i].strip().startswith("@") or not lines[i].strip()):
                if lines[i].strip().startswith("@") and "@staticmethod" not in lines[i]:
                    # Remove class-level indentation from decorator
                    decorator_text = lines[i].strip()
                    decorators.append(decorator_text)
                i += 1

            # Now we should be at the 'async def test_' line
            if i < len(lines) and "async def test_" in lines[i]:
                # Extract method signature
                method_line = lines[i]

                # Remove class-level indentation
                method_text = method_line.strip()

                # Convert method name: test_user_signup_success stays the same
                # Already at function level, just remove indentation

                # Write decorators at module level (no indentation)
                for decorator in decorators:
                    new_lines.append(decorator)

                # Write function definition at module level
                new_lines.append(method_text)
                methods_converted += 1
                i += 1

                # Copy function body with reduced indentation
                # Original body has method_indent + 4 spaces
                # New body should have 4 spaces (function body indent)

                original_body_indent = method_indent + 4

                while i < len(lines):
                    body_line = lines[i]

                    # Check if we've reached the next test method or end of class
                    if (
                        body_line.strip().startswith("@pytest.mark.")
                        or body_line.strip().startswith("@staticmethod")
                        or (
                            body_line.strip().startswith("class ")
                            and body_line.strip().endswith(":")
                        )
                        or (
                            body_line
                            and len(body_line) - len(body_line.lstrip()) < method_indent
                            and body_line.strip()
                        )
                    ):
                        # Next method or class, stop copying body
                        break

                    # Adjust indentation: remove class-level indent
                    if body_line.strip():  # Non-empty line
                        current_line_indent = len(body_line) - len(body_line.lstrip())
                        if current_line_indent >= original_body_indent:
                            # Remove class-level indentation
                            indent_reduction = method_indent
                            new_indent = current_line_indent - indent_reduction
                            new_lines.append(" " * new_indent + body_line.lstrip())
                        else:
                            # Empty or weirdly indented line, keep as-is
                            new_lines.append(body_line)
                    else:
                        # Empty line
                        new_lines.append(body_line)

                    i += 1

                # Add blank line between functions
                new_lines.append("")
                new_lines.append("")

                continue

        # Regular line (not in class or before class)
        if not in_class:
            new_lines.append(line)

        i += 1

    # Write converted content
    file_path.write_text("\n".join(new_lines))

    return classes_removed, methods_converted


def main():
    test_files = [
        Path("tests/integration/test_auth_registration.py"),
        Path("tests/integration/test_auth_login.py"),
        Path("tests/integration/test_tokens.py"),
        Path("tests/integration/test_mfa.py"),
    ]

    print("🔄 Converting class-based tests to function-based tests")
    print("=" * 70)

    total_classes = 0
    total_methods = 0

    for file_path in test_files:
        if file_path.exists():
            classes, methods = convert_test_file(file_path)
            total_classes += classes
            total_methods += methods
            print(f"✅ {file_path.name}:")
            print(f"   - Removed {classes} test classes")
            print(f"   - Converted {methods} test methods to functions")

    print("=" * 70)
    print(f"✅ Conversion complete!")
    print(f"   Total classes removed: {total_classes}")
    print(f"   Total functions created: {total_methods}")
    print("\nThis resolves pytest async fixture injection issues.")
    print("Tests should now execute properly with async fixtures.")

    return 0


if __name__ == "__main__":
    exit(main())
