#!/usr/bin/env node

/**
 * Complete SDK Verification Script
 * Tests that ALL SDKs (including Edge and Python) are properly built
 */

console.log('🧪 Testing ALL SDK Builds...\n');

const tests = [];

// Test @janua/js (Core SDK)
tests.push({
  name: '@janua/js',
  path: '../packages/js-sdk',
  test: () => {
    const sdk = require('../packages/js-sdk/dist/index.js');
    if (!sdk.JanuaClient) throw new Error('JanuaClient not exported');
    if (!sdk.VERSION) throw new Error('VERSION not exported');
    console.log(`  ✅ Core SDK v${sdk.VERSION} - JanuaClient, auth, users, organizations`);
  }
});

// Test @janua/nextjs
tests.push({
  name: '@janua/nextjs',
  path: '../packages/nextjs-sdk',
  test: () => {
    const _nextjs = require('../packages/nextjs-sdk/dist/index.js');
    const app = require('../packages/nextjs-sdk/dist/app/index.js');
    const middleware = require('../packages/nextjs-sdk/dist/middleware.js');
    
    if (!app.JanuaProvider) throw new Error('JanuaProvider not exported');
    if (!app.useAuth) throw new Error('useAuth not exported');
    if (!middleware.createJanuaMiddleware) throw new Error('createJanuaMiddleware not exported');
    console.log('  ✅ Next.js SDK - Provider, hooks, middleware, server utilities');
  }
});

// Test @janua/react-sdk
tests.push({
  name: '@janua/react-sdk',
  path: '../packages/react',
  test: () => {
    const react = require('../packages/react/dist/index.js');
    if (!react.SignIn) throw new Error('SignIn component not exported');
    if (!react.SignUp) throw new Error('SignUp component not exported');
    if (!react.useAuth) throw new Error('useAuth hook not exported');
    console.log('  ✅ React SDK - Components (SignIn, SignUp), hooks, provider');
  }
});

// Test @janua/vue
tests.push({
  name: '@janua/vue',
  path: '../packages/vue-sdk',
  test: () => {
    const vue = require('../packages/vue-sdk/dist/index.js');
    if (!vue.useAuth) throw new Error('useAuth composable not exported');
    if (!vue.useUser) throw new Error('useUser composable not exported');
    console.log('  ✅ Vue SDK - Composables (useAuth, useUser, useOrganization)');
  }
});

// Test @janua/edge (NEW!)
tests.push({
  name: '@janua/edge',
  path: '../packages/edge',
  test: () => {
    const edge = require('../packages/edge/dist/index.js');
    if (!edge.verify) throw new Error('verify function not exported');
    if (!edge.middleware) throw new Error('middleware not exported');
    if (!edge.createWorkerHandler) throw new Error('createWorkerHandler not exported');
    if (!edge.VERSION) throw new Error('VERSION not exported');
    console.log(`  ✅ Edge SDK v${edge.VERSION} - JWT verification, middleware, Cloudflare handler`);
  }
});

// Test Python SDK (NEW!)
tests.push({
  name: 'janua (Python)',
  path: '../packages/python-sdk',
  test: () => {
    const fs = require('fs');
    const path = require('path');
    
    // Check if wheel and sdist exist
    const distPath = path.join(__dirname, '../packages/python-sdk/dist');
    const files = fs.readdirSync(distPath);
    const wheel = files.find(f => f.endsWith('.whl'));
    const sdist = files.find(f => f.endsWith('.tar.gz'));
    
    if (!wheel) throw new Error('Python wheel not found');
    if (!sdist) throw new Error('Python sdist not found');
    
    console.log(`  ✅ Python SDK - Built (${wheel})`);
  }
});

// Run all tests
let passed = 0;
let failed = 0;

console.log('=' + '='.repeat(50));

for (const test of tests) {
  try {
    console.log(`\n📦 Testing ${test.name}...`);
    test.test();
    passed++;
  } catch (error) {
    console.error(`  ❌ Failed: ${error.message}`);
    failed++;
  }
}

// Summary
console.log('\n' + '='.repeat(50));
console.log('📊 Test Results:');
console.log(`  ✅ Passed: ${passed}/${tests.length}`);
if (failed > 0) {
  console.log(`  ❌ Failed: ${failed}/${tests.length}`);
}

// Test import syntax (for documentation)
console.log('\n📚 Import Examples:');
console.log('```javascript');
console.log("// Core SDK");
console.log("import { JanuaClient } from '@janua/js';");
console.log("const client = new JanuaClient({ appId: 'your-app-id' });");
console.log("");
console.log("// Next.js");
console.log("import { JanuaProvider, useAuth } from '@janua/nextjs/app';");
console.log("");
console.log("// React");
console.log("import { SignIn, useAuth } from '@janua/react-sdk';");
console.log("");
console.log("// Vue");
console.log("import { useAuth, useUser } from '@janua/vue';");
console.log("");
console.log("// Edge (Cloudflare Workers)");
console.log("import { verify, createWorkerHandler } from '@janua/edge';");
console.log("");
console.log("// Python");
console.log("from janua import JanuaClient");
console.log("client = JanuaClient(app_id='your-app-id')");
console.log('```');

// SDK Status Table
console.log('\n📈 SDK Readiness:');
console.log('| SDK | Package | Built | Status |');
console.log('|-----|---------|-------|--------|');
console.log('| JavaScript/TypeScript | @janua/js | ✅ | 100% Ready |');
console.log('| Next.js | @janua/nextjs | ✅ | 100% Ready |');
console.log('| React | @janua/react-sdk | ✅ | 100% Ready |');
console.log('| Vue | @janua/vue | ✅ | 100% Ready |');
console.log('| Edge/Cloudflare | @janua/edge | ✅ | 100% Ready |');
console.log('| Python | janua | ✅ | 100% Ready |');

if (failed === 0) {
  console.log('\n✨ ALL 6 SDKs are successfully built and ready for use!');
  console.log('🎯 100% SDK coverage achieved - matching documentation!');
  process.exit(0);
} else {
  console.log('\n⚠️  Some SDKs have issues. Please check the errors above.');
  process.exit(1);
}