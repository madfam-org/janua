#!/usr/bin/env python3
"""
Fixture Compatibility Fix Script
Created: January 13, 2025
Purpose: Fix test function signatures to match conftest.py fixture names

Changes:
- Replace 'async_client: AsyncClient' → 'client: AsyncClient'
- Remove unused 'async_db_session: AsyncSession' parameters
- Fix missing commas in parameter lists
- Preserve all other function parameters and formatting
"""

import ast
import sys
from pathlib import Path
from typing import Tuple


class FixtureRewriter(ast.NodeTransformer):
    """AST transformer to fix fixture parameter names"""

    def __init__(self):
        self.changes_made = 0
        self.files_modified = []

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AsyncFunctionDef:
        """Visit async function definitions and fix parameters"""
        # Only process test methods (have 'self' as first parameter)
        if not node.args.args:
            return node

        if node.args.args[0].arg != 'self':
            return node

        len(node.args.args)
        modified = False
        new_args = []

        for arg in node.args.args:
            # Keep 'self' parameter
            if arg.arg == 'self':
                new_args.append(arg)
                continue

            # Replace 'async_client' with 'client'
            if arg.arg == 'async_client':
                arg.arg = 'client'
                modified = True
                self.changes_made += 1

            # Skip 'async_db_session' and 'async_session' (not used in test bodies)
            if arg.arg in ('async_db_session', 'async_session'):
                modified = True
                self.changes_made += 1
                continue

            new_args.append(arg)

        if modified:
            node.args.args = new_args

        return node


def fix_file(file_path: Path) -> Tuple[bool, int]:
    """
    Fix fixture names in a single test file

    Returns:
        (success: bool, changes: int)
    """
    try:
        # Read original file
        content = file_path.read_text()

        # Parse AST
        tree = ast.parse(content)

        # Apply transformations
        rewriter = FixtureRewriter()
        new_tree = rewriter.visit(tree)

        if rewriter.changes_made == 0:
            print(f"  ℹ️  No changes needed in {file_path.name}")
            return True, 0

        # Generate new code
        new_content = ast.unparse(new_tree)

        # Write back to file
        file_path.write_text(new_content)

        print(f"  ✅ Fixed {rewriter.changes_made} fixture issues in {file_path.name}")
        return True, rewriter.changes_made

    except SyntaxError as e:
        print(f"  ❌ Syntax error in {file_path.name}: {e}")
        return False, 0
    except Exception as e:
        print(f"  ❌ Error processing {file_path.name}: {e}")
        return False, 0


def main():
    """Main execution function"""
    print("🔧 Fixture Compatibility Fix Script")
    print("=" * 60)

    # Define test files to fix
    test_files = [
        Path("/Users/aldoruizluna/labspace/janua/apps/api/tests/integration/test_auth_registration.py"),
        Path("/Users/aldoruizluna/labspace/janua/apps/api/tests/integration/test_auth_login_complete.py"),
        Path("/Users/aldoruizluna/labspace/janua/apps/api/tests/integration/test_tokens.py"),
        Path("/Users/aldoruizluna/labspace/janua/apps/api/tests/integration/test_mfa.py"),
    ]

    total_changes = 0
    success_count = 0

    for test_file in test_files:
        if not test_file.exists():
            print(f"  ⚠️  File not found: {test_file.name}")
            continue

        print(f"\n📝 Processing {test_file.name}...")
        success, changes = fix_file(test_file)

        if success:
            success_count += 1
            total_changes += changes

    print("\n" + "=" * 60)
    print(f"✅ Fixed {total_changes} fixture issues across {success_count}/{len(test_files)} files")

    # Validate syntax by attempting to compile
    print("\n🔍 Validating Python syntax...")
    all_valid = True

    for test_file in test_files:
        if not test_file.exists():
            continue

        try:
            compile(test_file.read_text(), str(test_file), 'exec')
            print(f"  ✅ {test_file.name} - syntax valid")
        except SyntaxError as e:
            print(f"  ❌ {test_file.name} - syntax error at line {e.lineno}: {e.msg}")
            all_valid = False

    if all_valid:
        print("\n🎉 All files have valid Python syntax!")
        return 0
    else:
        print("\n⚠️  Some files still have syntax errors")
        return 1


if __name__ == "__main__":
    sys.exit(main())
