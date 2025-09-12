#!/usr/bin/env node

/**
 * SDK Build Verification Script
 * Tests that all SDKs are properly built and importable
 */

console.log('🧪 Testing SDK Builds...\n');

const tests = [];

// Test @plinto/js (Core SDK)
tests.push({
  name: '@plinto/js',
  path: '../packages/js-sdk',
  test: () => {
    const sdk = require('../packages/js-sdk/dist/index.js');
    if (!sdk.PlintoClient) throw new Error('PlintoClient not exported');
    if (!sdk.VERSION) throw new Error('VERSION not exported');
    console.log(`  ✅ Core SDK v${sdk.VERSION} - PlintoClient, auth, users, organizations`);
  }
});

// Test @plinto/nextjs
tests.push({
  name: '@plinto/nextjs',
  path: '../packages/nextjs-sdk',
  test: () => {
    const nextjs = require('../packages/nextjs-sdk/dist/index.js');
    const app = require('../packages/nextjs-sdk/dist/app/index.js');
    const middleware = require('../packages/nextjs-sdk/dist/middleware.js');
    
    if (!app.PlintoProvider) throw new Error('PlintoProvider not exported');
    if (!app.useAuth) throw new Error('useAuth not exported');
    if (!middleware.createPlintoMiddleware) throw new Error('createPlintoMiddleware not exported');
    console.log('  ✅ Next.js SDK - Provider, hooks, middleware, server utilities');
  }
});

// Test @plinto/react
tests.push({
  name: '@plinto/react',
  path: '../packages/react',
  test: () => {
    const react = require('../packages/react/dist/index.js');
    if (!react.SignIn) throw new Error('SignIn component not exported');
    if (!react.SignUp) throw new Error('SignUp component not exported');
    if (!react.useAuth) throw new Error('useAuth hook not exported');
    console.log('  ✅ React SDK - Components (SignIn, SignUp), hooks, provider');
  }
});

// Test @plinto/vue
tests.push({
  name: '@plinto/vue',
  path: '../packages/vue-sdk',
  test: () => {
    const vue = require('../packages/vue-sdk/dist/index.js');
    if (!vue.PlintoPlugin) throw new Error('PlintoPlugin not exported');
    if (!vue.useAuth) throw new Error('useAuth composable not exported');
    if (!vue.useUser) throw new Error('useUser composable not exported');
    console.log('  ✅ Vue SDK - Plugin, composables (useAuth, useUser, useOrganization)');
  }
});

// Run all tests
let passed = 0;
let failed = 0;

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
console.log("import { PlintoClient } from '@plinto/js';");
console.log("const client = new PlintoClient({ appId: 'your-app-id' });");
console.log("");
console.log("// Next.js");
console.log("import { PlintoProvider, useAuth } from '@plinto/nextjs/app';");
console.log("");
console.log("// React");
console.log("import { SignIn, useAuth } from '@plinto/react';");
console.log("");
console.log("// Vue");
console.log("import { PlintoPlugin } from '@plinto/vue';");
console.log("app.use(PlintoPlugin, { appId: 'your-app-id' });");
console.log('```');

if (failed === 0) {
  console.log('\n✨ All SDKs are successfully built and ready for use!');
  process.exit(0);
} else {
  console.log('\n⚠️  Some SDKs have issues. Please check the errors above.');
  process.exit(1);
}