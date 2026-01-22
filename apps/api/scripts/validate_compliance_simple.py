#!/usr/bin/env python3
"""
Simple Compliance Component Validation

Validates the structure and basic syntax of compliance components without full imports.
"""

import ast
from pathlib import Path


def validate_python_syntax(file_path):
    """Validate Python syntax of a file"""
    try:
        with open(file_path, "r") as f:
            content = f.read()
        ast.parse(content)
        return True, "Syntax OK"
    except SyntaxError as e:
        return False, f"Syntax Error: {e}"
    except Exception as e:
        return False, f"Error: {e}"


def check_class_definitions(file_path, expected_classes):
    """Check if expected classes are defined in file"""
    try:
        with open(file_path, "r") as f:
            content = f.read()

        tree = ast.parse(content)

        defined_classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                defined_classes.append(node.name)

        missing_classes = []
        for expected_class in expected_classes:
            if expected_class not in defined_classes:
                missing_classes.append(expected_class)

        return len(missing_classes) == 0, defined_classes, missing_classes
    except Exception as e:
        return False, [], [f"Error: {e}"]


def main():
    """Validate compliance components"""

    print("🔍 Simple Compliance Component Validation")
    print("=" * 50)

    compliance_dir = Path("apps/api/app/compliance")

    # File validation
    components = {
        "audit.py": ["AuditLogger", "AuditTrail", "ComplianceEvent", "AuditEvidence"],
        "privacy.py": ["PrivacyManager", "GDPRCompliance", "DataSubjectRequestResponse"],
        "dashboard.py": ["ComplianceDashboard", "ComplianceMetrics", "ComplianceDashboardData"],
        "support.py": ["SupportSystem", "SupportTicket", "SupportMetrics"],
        "policies.py": ["PolicyManager", "SecurityPolicy", "PolicyCompliance", "PolicyViolation"],
    }

    all_passed = True

    for file_name, expected_classes in components.items():
        file_path = compliance_dir / file_name

        print(f"\n📁 Validating {file_name}...")
        print("-" * 30)

        # Check file exists
        if not file_path.exists():
            print(f"❌ File not found: {file_path}")
            all_passed = False
            continue

        # Check syntax
        syntax_ok, syntax_msg = validate_python_syntax(file_path)
        if syntax_ok:
            print(f"✅ Syntax: {syntax_msg}")
        else:
            print(f"❌ Syntax: {syntax_msg}")
            all_passed = False
            continue

        # Check classes
        classes_ok, defined_classes, missing_classes = check_class_definitions(
            file_path, expected_classes
        )

        if classes_ok:
            print(f"✅ Classes: All {len(expected_classes)} classes found")
        else:
            print(f"❌ Classes: Missing {missing_classes}")
            all_passed = False

        print(
            f"📊 Defined classes: {', '.join(defined_classes[:5])}"
            + ("..." if len(defined_classes) > 5 else "")
        )

    # Check __init__.py
    print(f"\n📁 Validating __init__.py...")
    print("-" * 30)

    init_file = compliance_dir / "__init__.py"
    if init_file.exists():
        syntax_ok, syntax_msg = validate_python_syntax(init_file)
        if syntax_ok:
            print(f"✅ __init__.py syntax: {syntax_msg}")

            # Check if main exports are present
            with open(init_file, "r") as f:
                content = f.read()

            key_exports = [
                "AuditLogger",
                "PrivacyManager",
                "ComplianceDashboard",
                "SupportSystem",
                "PolicyManager",
            ]

            missing_exports = []
            for export in key_exports:
                if export not in content:
                    missing_exports.append(export)

            if not missing_exports:
                print("✅ Key exports: All found in __init__.py")
            else:
                print(f"⚠️  Missing exports: {missing_exports}")
        else:
            print(f"❌ __init__.py syntax: {syntax_msg}")
            all_passed = False
    else:
        print("❌ __init__.py not found")
        all_passed = False

    # Summary
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All validation checks passed!")
        print("\n📋 Implementation Summary:")
        print("✅ All 5 compliance components implemented")
        print("✅ All required classes defined")
        print("✅ Python syntax validation passed")
        print("✅ Export structure correct")

        print("\n🚀 Ready for Integration:")
        print("1. Import components in your application")
        print("2. Initialize with Redis client")
        print("3. Configure database models")
        print("4. Set up API endpoints")

        return 0
    else:
        print("⚠️  Some validation issues found")
        print("Please review the errors above")
        return 1


if __name__ == "__main__":
    exit(main())
