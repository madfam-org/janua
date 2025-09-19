/**
 * Integration Test Suite - Package Installation
 * 
 * Tests that all published packages can be installed and imported correctly
 * by third-party developers.
 */

const { exec } = require('child_process');
const { promisify } = require('util');
const fs = require('fs').promises;
const path = require('path');
const os = require('os');

const execAsync = promisify(exec);

describe('Package Installation Tests', () => {
  let testDir;

  beforeEach(async () => {
    // Create temporary test directory
    testDir = await fs.mkdtemp(path.join(os.tmpdir(), 'plinto-test-'));
    
    // Initialize package.json
    await fs.writeFile(
      path.join(testDir, 'package.json'),
      JSON.stringify({
        name: 'plinto-integration-test',
        version: '1.0.0',
        type: 'module'
      }, null, 2)
    );
  });

  afterEach(async () => {
    // Clean up test directory
    if (testDir) {
      await fs.rm(testDir, { recursive: true, force: true });
    }
  });

  describe('TypeScript SDK', () => {
    test('should install and import successfully', async () => {
      // Install package
      const { stdout, stderr } = await execAsync(
        'npm install @plinto/typescript-sdk',
        { cwd: testDir }
      );
      
      expect(stderr).not.toContain('error');

      // Test import
      const testFile = `
        import { PlintoClient } from '@plinto/typescript-sdk';
        
        const client = new PlintoClient({
          baseURL: 'https://api.plinto.dev'
        });
        
        console.log('SUCCESS: TypeScript SDK imported');
      `;
      
      await fs.writeFile(path.join(testDir, 'test.mjs'), testFile);
      
      const { stdout: output } = await execAsync(
        'node test.mjs',
        { cwd: testDir }
      );
      
      expect(output).toContain('SUCCESS: TypeScript SDK imported');
    }, 30000);

    test('should provide TypeScript types', async () => {
      await execAsync('npm install @plinto/typescript-sdk typescript', { cwd: testDir });
      
      const tsFile = `
        import { PlintoClient, User, Session } from '@plinto/typescript-sdk';
        
        const client: PlintoClient = new PlintoClient({
          baseURL: 'https://api.plinto.dev'
        });
        
        const user: User = {
          id: 'usr_123',
          email: 'test@example.com',
          emailVerified: false,
          createdAt: new Date().toISOString()
        };
      `;
      
      await fs.writeFile(path.join(testDir, 'test.ts'), tsFile);
      
      // Type check
      const { stderr } = await execAsync(
        'npx tsc --noEmit test.ts',
        { cwd: testDir }
      );
      
      expect(stderr).toBe('');
    }, 30000);
  });

  describe('React SDK', () => {
    test('should install with peer dependencies', async () => {
      const { stderr } = await execAsync(
        'npm install @plinto/react-sdk react react-dom',
        { cwd: testDir }
      );
      
      expect(stderr).not.toContain('error');
      
      // Check package is installed
      const packageJson = await fs.readFile(
        path.join(testDir, 'package.json'),
        'utf-8'
      );
      const pkg = JSON.parse(packageJson);
      
      expect(pkg.dependencies).toHaveProperty('@plinto/react-sdk');
      expect(pkg.dependencies).toHaveProperty('react');
    }, 30000);

    test('should export React hooks', async () => {
      await execAsync(
        'npm install @plinto/react-sdk react react-dom',
        { cwd: testDir }
      );
      
      const testFile = `
        import { useAuth, useUser, PlintoProvider } from '@plinto/react-sdk';
        
        if (typeof useAuth === 'function') {
          console.log('SUCCESS: React hooks exported');
        }
      `;
      
      await fs.writeFile(path.join(testDir, 'test.mjs'), testFile);
      
      const { stdout } = await execAsync('node test.mjs', { cwd: testDir });
      
      expect(stdout).toContain('SUCCESS: React hooks exported');
    }, 30000);
  });

  describe('Python SDK', () => {
    test('should install via pip', async () => {
      const { stderr } = await execAsync(
        'pip install plinto-sdk',
        { cwd: testDir }
      );
      
      expect(stderr).not.toContain('ERROR');
      
      // Test import
      const pythonTest = `
import sys
try:
    from plinto import PlintoClient
    print("SUCCESS: Python SDK imported")
except ImportError as e:
    print(f"ERROR: {e}")
    sys.exit(1)
      `;
      
      await fs.writeFile(path.join(testDir, 'test.py'), pythonTest);
      
      const { stdout } = await execAsync('python test.py', { cwd: testDir });
      
      expect(stdout).toContain('SUCCESS: Python SDK imported');
    }, 30000);
  });

  describe('Cross-Package Compatibility', () => {
    test('should work together in same project', async () => {
      // Install multiple packages
      await execAsync(
        'npm install @plinto/typescript-sdk @plinto/core @plinto/jwt-utils',
        { cwd: testDir }
      );
      
      const testFile = `
        import { PlintoClient } from '@plinto/typescript-sdk';
        import { validateJWT } from '@plinto/jwt-utils';
        
        const client = new PlintoClient({
          baseURL: 'https://api.plinto.dev'
        });
        
        console.log('SUCCESS: Multiple packages work together');
      `;
      
      await fs.writeFile(path.join(testDir, 'test.mjs'), testFile);
      
      const { stdout, stderr } = await execAsync('node test.mjs', { cwd: testDir });
      
      expect(stderr).toBe('');
      expect(stdout).toContain('SUCCESS: Multiple packages work together');
    }, 30000);
  });
});

describe('Package Build Tests', () => {
  test('TypeScript SDK should have built distributions', async () => {
    const distPath = path.join(__dirname, '../../packages/typescript-sdk/dist');
    const distExists = await fs.access(distPath).then(() => true).catch(() => false);
    
    expect(distExists).toBe(true);
    
    if (distExists) {
      const files = await fs.readdir(distPath);
      expect(files).toContain('index.js');
      expect(files).toContain('index.esm.js');
      expect(files).toContain('index.d.ts');
    }
  });

  test('All packages should have consistent versions', async () => {
    const packagesDir = path.join(__dirname, '../../packages');
    const packages = await fs.readdir(packagesDir);
    
    const versions = new Set();
    
    for (const pkg of packages) {
      const packageJsonPath = path.join(packagesDir, pkg, 'package.json');
      try {
        const content = await fs.readFile(packageJsonPath, 'utf-8');
        const { version, private: isPrivate } = JSON.parse(content);
        
        if (!isPrivate) {
          versions.add(version);
        }
      } catch (err) {
        // Skip if no package.json
      }
    }
    
    // All public packages should have same version
    expect(versions.size).toBe(1);
    expect(versions.has('1.0.0')).toBe(true);
  });
});

describe('Example Application Tests', () => {
  test('Next.js example should have all dependencies', async () => {
    const examplePath = path.join(__dirname, '../../examples/nextjs-app/package.json');
    const content = await fs.readFile(examplePath, 'utf-8');
    const pkg = JSON.parse(content);
    
    expect(pkg.dependencies).toHaveProperty('@plinto/nextjs-sdk');
    expect(pkg.dependencies).toHaveProperty('@plinto/react-sdk');
    expect(pkg.dependencies).toHaveProperty('@plinto/typescript-sdk');
    expect(pkg.dependencies).toHaveProperty('next');
    expect(pkg.dependencies).toHaveProperty('react');
  });

  test('Example components should exist', async () => {
    const componentsPath = path.join(__dirname, '../../examples/nextjs-app/app/components');
    const components = await fs.readdir(componentsPath);
    
    expect(components).toContain('LoginForm.tsx');
    expect(components).toContain('UserProfile.tsx');
    expect(components).toContain('Dashboard.tsx');
  });
});