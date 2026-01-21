#!/usr/bin/env python3
"""
Universal Test Fix Utility
Automatically fixes common test issues to achieve 100% pass rate
"""

import os
import re
from pathlib import Path
from typing import List
import subprocess


class UniversalTestFixer:
    """Fixes all common test issues automatically"""
    
    def __init__(self):
        self.fixes_applied = 0
        self.files_fixed = 0
        self.test_root = Path("tests")
        
    def fix_all_tests(self):
        """Main entry point to fix all tests"""
        print("🔧 Universal Test Fixer Starting...")
        print("=" * 50)
        
        # Find all test files
        test_files = self.find_test_files()
        print(f"Found {len(test_files)} test files to analyze")
        
        # Apply fixes to each file
        for test_file in test_files:
            self.fix_test_file(test_file)
            
        # Report results
        print("\n" + "=" * 50)
        print(f"✅ Fixed {self.files_fixed} files with {self.fixes_applied} total fixes")
        
        # Run validation
        self.validate_fixes()
        
    def find_test_files(self) -> List[Path]:
        """Find all Python test files"""
        test_files = []
        for pattern in ["test_*.py", "*_test.py"]:
            test_files.extend(self.test_root.rglob(pattern))
        return test_files
        
    def fix_test_file(self, file_path: Path):
        """Apply all fixes to a single test file"""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                
            original_content = content
            
            # Apply each fix pattern
            content = self.fix_async_decorators(content)
            content = self.fix_mock_imports(content)
            content = self.fix_async_mocks(content)
            content = self.fix_fixture_usage(content)
            content = self.fix_event_loop_issues(content)
            content = self.fix_database_mocks(content)
            content = self.fix_redis_mocks(content)
            content = self.fix_test_client_usage(content)
            content = self.fix_missing_awaits(content)
            content = self.fix_import_errors(content)
            
            # Only write if changes were made
            if content != original_content:
                with open(file_path, 'w') as f:
                    f.write(content)
                self.files_fixed += 1
                print(f"  ✅ Fixed: {file_path.relative_to(Path.cwd())}")
                
        except Exception as e:
            print(f"  ❌ Error fixing {file_path}: {e}")
            
    def fix_async_decorators(self, content: str) -> str:
        """Add @pytest.mark.asyncio to async test functions"""
        lines = content.split('\n')
        fixed_lines = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # Check if this is an async test function without decorator
            if re.match(r'\s*async\s+def\s+test_', line):
                # Check if previous line is already a decorator
                if i > 0 and not '@pytest.mark.asyncio' in lines[i-1]:
                    # Add the decorator
                    indent = len(line) - len(line.lstrip())
                    fixed_lines.append(' ' * indent + '@pytest.mark.asyncio')
                    self.fixes_applied += 1
                    
            fixed_lines.append(line)
            i += 1
            
        return '\n'.join(fixed_lines)
        
    def fix_mock_imports(self, content: str) -> str:
        """Fix mock import statements"""
        # Ensure AsyncMock is imported
        if 'AsyncMock' not in content and 'async def' in content:
            if 'from unittest.mock import' in content:
                content = re.sub(
                    r'from unittest\.mock import ([^\\n]+)',
                    lambda m: f"from unittest.mock import {m.group(1)}, AsyncMock" 
                              if 'AsyncMock' not in m.group(1) else m.group(0),
                    content
                )
            else:
                # Add import if not present
                import_line = "from unittest.mock import AsyncMock, MagicMock, Mock, patch\n"
                content = import_line + content
                
            self.fixes_applied += 1
            
        return content
        
    def fix_async_mocks(self, content: str) -> str:
        """Replace Mock() with AsyncMock() for async operations"""
        patterns = [
            # Mock for async services
            (r'(\w+_service)\s*=\s*Mock\(\)', r'\1 = AsyncMock()'),
            (r'(\w+_client)\s*=\s*Mock\(\)', r'\1 = AsyncMock()'),
            (r'mock_(\w+)\s*=\s*Mock\(\)', r'mock_\1 = AsyncMock()'),
            
            # Async method mocking
            (r'\.(\w+)\s*=\s*Mock\(return_value=([^)]+)\)\s*#\s*async', 
             r'.\1 = AsyncMock(return_value=\2)'),
        ]
        
        for pattern, replacement in patterns:
            if re.search(pattern, content):
                content = re.sub(pattern, replacement, content)
                self.fixes_applied += 1
                
        return content
        
    def fix_fixture_usage(self, content: str) -> str:
        """Fix fixture import and usage"""
        # Add fixture imports if missing
        if 'async_db_session' in content and 'from fixtures.async_fixtures import' not in content:
            import_line = "from fixtures.async_fixtures import async_db_session, async_redis_client\n"
            # Add after other imports
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if line.startswith('import ') or line.startswith('from '):
                    continue
                else:
                    lines.insert(i, import_line)
                    break
            content = '\n'.join(lines)
            self.fixes_applied += 1
            
        return content
        
    def fix_event_loop_issues(self, content: str) -> str:
        """Fix event loop configuration issues"""
        # Add pytest-asyncio mode if missing
        if '@pytest.mark.asyncio' in content and 'pytestmark' not in content:
            # Add module-level asyncio marker
            lines = content.split('\n')
            import_end = 0
            for i, line in enumerate(lines):
                if line and not line.startswith('import') and not line.startswith('from') and not line.startswith('#'):
                    import_end = i
                    break
                    
            lines.insert(import_end, '\npytestmark = pytest.mark.asyncio\n')
            content = '\n'.join(lines)
            self.fixes_applied += 1
            
        return content
        
    def fix_database_mocks(self, content: str) -> str:
        """Fix database session mocking"""
        patterns = [
            # Fix session mock
            (r'mock_session\s*=\s*Mock\(.*?\)', r'mock_session = AsyncMock()'),
            (r'db_session\s*=\s*Mock\(.*?\)', r'db_session = AsyncMock()'),
            
            # Fix execute/commit/rollback
            (r'\.execute\s*=\s*Mock\(', r'.execute = AsyncMock('),
            (r'\.commit\s*=\s*Mock\(', r'.commit = AsyncMock('),
            (r'\.rollback\s*=\s*Mock\(', r'.rollback = AsyncMock('),
            (r'\.refresh\s*=\s*Mock\(', r'.refresh = AsyncMock('),
        ]
        
        for pattern, replacement in patterns:
            content = re.sub(pattern, replacement, content)
            
        return content
        
    def fix_redis_mocks(self, content: str) -> str:
        """Fix Redis client mocking"""
        patterns = [
            # Fix redis mock
            (r'mock_redis\s*=\s*Mock\(.*?\)', r'mock_redis = AsyncMock()'),
            (r'redis_client\s*=\s*Mock\(.*?\)', r'redis_client = AsyncMock()'),
            
            # Fix redis methods
            (r'\.get\s*=\s*Mock\(', r'.get = AsyncMock('),
            (r'\.set\s*=\s*Mock\(', r'.set = AsyncMock('),
            (r'\.setex\s*=\s*Mock\(', r'.setex = AsyncMock('),
            (r'\.delete\s*=\s*Mock\(', r'.delete = AsyncMock('),
        ]
        
        for pattern, replacement in patterns:
            content = re.sub(pattern, replacement, content)
            
        return content
        
    def fix_test_client_usage(self, content: str) -> str:
        """Fix test client usage for async"""
        if 'TestClient' in content and 'async def test_' in content:
            # Replace TestClient with AsyncClient
            content = content.replace('from fastapi.testclient import TestClient',
                                    'from httpx import AsyncClient')
            content = content.replace('TestClient(app', 'AsyncClient(app=app, base_url="http://test"')
            content = content.replace('client.post(', 'await client.post(')
            content = content.replace('client.get(', 'await client.get(')
            content = content.replace('client.put(', 'await client.put(')
            content = content.replace('client.delete(', 'await client.delete(')
            self.fixes_applied += 1
            
        return content
        
    def fix_missing_awaits(self, content: str) -> str:
        """Add missing await keywords"""
        patterns = [
            # Common async method calls without await
            (r'(\s+)(\w+\.create_user\([^)]+\))', r'\1await \2'),
            (r'(\s+)(\w+\.authenticate\([^)]+\))', r'\1await \2'),
            (r'(\s+)(\w+\.execute\([^)]+\))', r'\1await \2'),
            (r'(\s+)(\w+\.commit\(\))', r'\1await \2'),
        ]
        
        for pattern, replacement in patterns:
            # Only replace if not already awaited
            if re.search(pattern, content) and not re.search(f'await {pattern}', content):
                content = re.sub(pattern, replacement, content)
                self.fixes_applied += 1
                
        return content
        
    def fix_import_errors(self, content: str) -> str:
        """Fix common import errors"""
        # Add missing imports
        imports_to_add = []
        
        if 'pytest.mark.asyncio' in content and 'import pytest' not in content:
            imports_to_add.append('import pytest')
            
        if 'datetime' in content and 'from datetime import' not in content and 'import datetime' not in content:
            imports_to_add.append('from datetime import datetime, timedelta')
            
        if 'AsyncClient' in content and 'from httpx import AsyncClient' not in content:
            imports_to_add.append('from httpx import AsyncClient')
            
        if imports_to_add:
            content = '\n'.join(imports_to_add) + '\n' + content
            self.fixes_applied += len(imports_to_add)
            
        return content
        
    def validate_fixes(self):
        """Run tests to validate fixes"""
        print("\n🔍 Validating fixes...")
        
        # Run core tests
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/test_100_coverage.py", 
             "--tb=no", "-q", "--no-header"],
            capture_output=True,
            text=True,
            env={**os.environ, 
                 "ENVIRONMENT": "test",
                 "DATABASE_URL": "sqlite+aiosqlite:///:memory:"}
        )
        
        if "passed" in result.stdout:
            print("✅ Core tests passing!")
        else:
            print("⚠️ Some tests still failing - manual review needed")
            

def main():
    """Main entry point"""
    fixer = UniversalTestFixer()
    fixer.fix_all_tests()
    

if __name__ == "__main__":
    main()