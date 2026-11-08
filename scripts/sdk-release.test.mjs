import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { PACKAGES, REGISTRY, validateRelease, resolveRequest, assertRegistryAbsent, inspectManifest, packRelease, publishRelease, ensureReleaseTag, ensurePublishedDependencies, satisfiesPublishedRange, command } from './sdk-release.mjs';

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const fixtureHead = 'a'.repeat(40);
const gitReply = args => ({ status: 0, stdout: args[0] === 'rev-parse' ? fixtureHead : '' });
const missing = { status: 1, stdout: JSON.stringify({ error: { code: 'E404' } }) };
function fixture() {
  const directory = mkdtempSync(join(tmpdir(), 'janua-release-test-'));
  writeFileSync(join(directory, 'package.json'), JSON.stringify({ private: true, packageManager: JSON.parse(readFileSync(join(root, 'package.json'))).packageManager }));
  writeFileSync(join(directory, 'pnpm-workspace.yaml'), "packages:\n  - 'packages/*'\n");
  const manifest = (name, data) => {
    const path = join(directory, 'packages', name); mkdirSync(path, { recursive: true });
    writeFileSync(join(path, 'package.json'), JSON.stringify({ name: PACKAGES[name], version: '1.2.3', ...data }));
    writeFileSync(join(path, 'index.js'), 'export const fixture = true;\n');
  };
  manifest('typescript-sdk', {}); manifest('ui', {});
  manifest('nextjs-sdk', { main: 'index.js', files: ['index.js'], dependencies: { '@janua/typescript-sdk': 'workspace:^', '@janua/ui': 'workspace:*' }, peerDependencies: { '@janua/core': '^1.0.0' } });
  return { directory, manifest, cleanup: () => rmSync(directory, { recursive: true, force: true }) };
}

for (const name of Object.keys(PACKAGES)) {
  test(`allowlisted manifest identity: ${name}`, () => {
    const f = fixture();
    try {
      f.manifest(name, {});
      assert.equal(validateRelease(f.directory, name, '1.2.3').packageName, PACKAGES[name]);
    } finally { f.cleanup(); }
  });
}
test('rejects path, shell and workflow-output injection, unsupported package, or mismatched version', () => {
  const f = fixture();
  try {
    for (const name of ['../apps/admin', 'nextjs-sdk; echo fixture', 'ui\nversion=9', 'python-sdk', '__proto__']) assert.throws(() => validateRelease(f.directory, name, '1.2.3'));
    for (const version of ['1.2.4', '01.2.3', '1.2.3-01', '1.2.3+metadata', '1.2.3\nignored=x', '$(echo fixture)']) assert.throws(() => validateRelease(f.directory, 'nextjs-sdk', version));
    f.manifest('nextjs-sdk', { private: true }); assert.throws(() => validateRelease(f.directory, 'nextjs-sdk', '1.2.3'));
    f.manifest('nextjs-sdk', { name: '@other/package' }); assert.throws(() => validateRelease(f.directory, 'nextjs-sdk', '1.2.3'));
  } finally { f.cleanup(); }
});
test('tag and dispatch validate the selected checkout; nextjs uses its actual registry name', () => {
  const f = fixture();
  try {
    const dispatch = resolveRequest(f.directory, { GITHUB_EVENT_NAME: 'workflow_dispatch', SDK_NAME: 'nextjs-sdk', SDK_VERSION: '1.2.3' });
    assert.equal(dispatch.packageName, '@janua/nextjs'); assert.equal(dispatch.releaseTag, 'nextjs-sdk-v1.2.3');
    assert.equal(resolveRequest(f.directory, { GITHUB_EVENT_NAME: 'push', GITHUB_REF: 'refs/tags/ui-v1.2.3' }).packageName, '@janua/ui');
    assert.throws(() => resolveRequest(f.directory, { GITHUB_EVENT_NAME: 'push', GITHUB_REF: 'refs/tags/ui-v9.0.0' }));
    f.manifest('ui', { version: '1.2.3-beta.1' });
    const prerelease = validateRelease(f.directory, 'ui', '1.2.3-beta.1');
    assert.equal(prerelease.distTag, 'next'); assert.equal(prerelease.prerelease, true);
  } finally { f.cleanup(); }
});
test('registry errors cannot masquerade as missing releases', () => {
  assert.doesNotThrow(() => assertRegistryAbsent(missing, '1.2.3'));
  for (const code of ['E401', 'E403', 'E500', 'ETIMEDOUT', 'ENOTFOUND']) assert.throws(() => assertRegistryAbsent({ status: 1, stdout: JSON.stringify({ error: { code } }) }, '1.2.3'));
  for (const result of [{ status: 0, stdout: '"1.2.3"' }, { status: 0, stdout: '' }, { status: 0, stdout: 'null' }, { status: 0, stdout: '"9.0.0"' }, { status: 1, stdout: '404' }, { status: null, stdout: missing.stdout }]) assert.throws(() => assertRegistryAbsent(result, '1.2.3'));
});
test('packed identity, entrypoints and every dependency section are checked', () => {
  const release = { packageName: '@janua/nextjs', version: '1.2.3' };
  const manifest = { name: release.packageName, version: release.version, main: './index.js' };
  const files = new Set(['package/index.js']);
  assert.doesNotThrow(() => inspectManifest(manifest, release, files));
  for (const section of ['dependencies', 'optionalDependencies', 'peerDependencies', 'devDependencies']) {
    for (const value of ['workspace:^', 'file:../other', 'link:../other', '../other', 'npm:@janua/core@workspace:*']) assert.throws(() => inspectManifest({ ...manifest, [section]: { '@janua/core': value } }, release, files));
  }
  for (const change of [{ name: '@other/name' }, { version: '1.2.4' }, { private: true }, { main: 'missing.js' }, { main: '../outside.js' }, { publishConfig: { registry: 'https://registry.npmjs.org' } }, { publishConfig: { tag: 'other' } }]) assert.throws(() => inspectManifest({ ...manifest, ...change }, release, files));
});
test('real pnpm pack rewrites workspace ranges; publish uses only its inspected tarball', () => {
  const f = fixture(); let metadata;
  const runPack = (binary, args, options) => {
    if (binary !== 'pnpm') return command(binary, args, options);
    const result = command('corepack', ['pnpm', ...args], { ...options, cwd: f.directory, env: { ...process.env, NPM_MADFAM_TOKEN: '' } });
    assert.equal(result.status, 0, result.stdout + result.stderr);
    return result;
  };
  try {
    const install = command('corepack', ['pnpm', 'install', '--offline', '--ignore-scripts', '--lockfile=false', '--config.auto-install-peers=false'], { cwd: f.directory, env: { ...process.env, NPM_MADFAM_TOKEN: '' } });
    assert.equal(install.status, 0, install.stdout + install.stderr);
    const release = validateRelease(f.directory, 'nextjs-sdk', '1.2.3');
    metadata = packRelease(release, runPack);
    const packed = JSON.parse(readFileSync(metadata));
    const manifest = JSON.parse(command('tar', ['-xOf', packed.tarball, 'package/package.json']).stdout);
    assert.equal(manifest.dependencies['@janua/typescript-sdk'], '^1.2.3');
    assert.equal(manifest.dependencies['@janua/ui'], '1.2.3');
    const npmCalls = [];
    const mockedPublisher = (binary, args, options) => {
      if (binary === 'git') return gitReply(args);
      if (binary !== 'npm') return command(binary, args, options);
      npmCalls.push(args);
      if (args[0] === 'view' && args[1] !== '@janua/nextjs@1.2.3') {
        const name = args[1].slice(0, args[1].lastIndexOf('@'));
        return { status: 0, stdout: JSON.stringify({ name, version: '1.2.3' }) };
      }
      return args[0] === 'view' ? missing : { status: 0, stdout: '' };
    };
    publishRelease(release, metadata, mockedPublisher);
    assert.deepEqual(npmCalls[0], ['view', '@janua/nextjs@1.2.3', 'version', '--json', '--registry', REGISTRY]);
    assert.deepEqual(npmCalls.at(-1), ['publish', packed.tarball, '--ignore-scripts', '--registry', REGISTRY, '--access', 'restricted', '--tag', 'latest']);
    let failedPublishCalls = 0;
    assert.throws(() => publishRelease(release, metadata, (binary, args, options) => {
      if (binary === 'git') return gitReply(args);
      if (binary !== 'npm') return command(binary, args, options);
      if (args[0] === 'view') return args[1] === '@janua/nextjs@1.2.3' ? missing : { status: 0, stdout: JSON.stringify({ name: args[1].slice(0, args[1].lastIndexOf('@')), version: '1.2.3' }) };
      failedPublishCalls++; return { status: 7, stdout: '' };
    }), /npm failed/);
    assert.equal(failedPublishCalls, 1);
    let unauthorizedPublishCalls = 0;
    assert.throws(() => publishRelease(release, metadata, (binary, args, options) => {
      if (binary === 'git') return gitReply(args);
      if (binary !== 'npm') return command(binary, args, options);
      if (args[0] === 'publish') unauthorizedPublishCalls++;
      return { status: 1, stdout: JSON.stringify({ error: { code: 'E403' } }) };
    }), /absence is not established/);
    assert.equal(unauthorizedPublishCalls, 0);
    const callsBeforeTamper = npmCalls.length;
    writeFileSync(packed.tarball, 'fixture-tampered');
    assert.throws(() => publishRelease(release, metadata, mockedPublisher), /changed after inspection/);
    assert.equal(npmCalls.length, callsBeforeTamper);
  } finally { if (metadata) rmSync(dirname(metadata), { recursive: true, force: true }); f.cleanup(); }
});
test('pack command errors stop before inspection or publication', () => {
  const f = fixture(); const calls = [];
  try {
    assert.throws(() => packRelease(validateRelease(f.directory, 'nextjs-sdk', '1.2.3'), (binary, args) => { calls.push([binary, args]); return { status: 2, stdout: '' }; }), /pnpm failed/);
    assert.equal(calls.length, 1); assert.equal(calls[0][0], 'pnpm');
  } finally { f.cleanup(); }
});
test('workflow requires dependency build, tests, validated inputs, inspected archive and correct release identity', () => {
  const workflow = readFileSync(join(root, '.github/workflows/publish-sdks.yml'), 'utf8');
  const npm = workflow.split('  publish-python:')[0];
  assert.match(npm, /startsWith\(github.ref, 'refs\/tags\/ui-v'\)/);
  assert.match(npm, /pnpm --filter "\$PACKAGE_NAME\.\.\.".*--workspace-concurrency=1 -r --if-present run build/);
  assert.match(npm, /pnpm --filter "\$PACKAGE_NAME" --fail-if-no-match test/);
  for (const mode of ['validate', 'registry', 'pack', 'publish']) assert.match(npm, new RegExp(`run: node scripts/sdk-release.mjs ${mode}`));
  assert.match(npm, /npm install \$\{\{ steps.extract.outputs.package_name \}\}@\$\{\{ steps.extract.outputs.version \}\}/);
  assert.match(npm, /target_commitish: \$\{\{ github.sha \}\}/);
  assert.doesNotMatch(npm, /continue-on-error|\|\| true|npm publish|ref:.*main/);
  assert.doesNotMatch(npm, /run:.*\$\{\{\s*inputs\./);
  const ci = readFileSync(join(root, '.github/workflows/ci.yml'), 'utf8');
  assert.match(ci.split('  lint:')[1].split('  cli-test:')[0], /run: node --test scripts\/sdk-release.test.mjs/);
  const retired = readFileSync(join(root, '.github/workflows/publish.yml'), 'utf8');
  assert.match(retired, /exit 1/);
  assert.doesNotMatch(retired, /secrets\.|uses:|git push|npm publish|twine upload|inputs\./);
});


test('remote tag provenance accepts absence or HEAD, peels annotated tags, and fails closed', () => {
  const release = { releaseTag: 'nextjs-sdk-v1.2.3' };
  const ref = `refs/tags/${release.releaseTag}`;
  const run = result => (binary, args) => {
    assert.equal(binary, 'git');
    if (args[0] === 'rev-parse') return { status: 0, stdout: fixtureHead };
    assert.deepEqual(args, ['ls-remote', '--tags', 'origin', ref, `${ref}^{}`]);
    return result;
  };
  for (const stdout of ['', `${fixtureHead}\t${ref}\n`, `${'b'.repeat(40)}\t${ref}\n${fixtureHead}\t${ref}^{}\n`]) assert.doesNotThrow(() => ensureReleaseTag(release, run({ status: 0, stdout })));
  for (const stdout of [`${'b'.repeat(40)}\t${ref}`, `${fixtureHead}\t${ref}\n${'b'.repeat(40)}\t${ref}^{}`, 'malformed']) assert.throws(() => ensureReleaseTag(release, run({ status: 0, stdout })));
  assert.throws(() => ensureReleaseTag(release, run({ status: 128, stdout: '' })), /git failed/);
});

test('runtime dependency gates include optional dependencies and aliases, excluding dev dependencies', () => {
  const queries = [];
  const manifest = {
    dependencies: { '@janua/typescript-sdk': '^1.2.3', alias: 'npm:@janua/ui@~1.2.0', external: '^1.0.0' },
    optionalDependencies: { '@janua/core': '1.2.3' },
    devDependencies: { '@janua/unpublished-dev': '^9.0.0' },
  };
  ensurePublishedDependencies(manifest, (binary, args) => {
    assert.equal(binary, 'npm'); queries.push(args[1]);
    assert.deepEqual(args.slice(2), ['--json', '--registry', REGISTRY]);
    return { status: 0, stdout: JSON.stringify({ name: args[1].slice(0, args[1].lastIndexOf('@')), version: '1.2.3' }) };
  });
  assert.deepEqual(queries, ['@janua/typescript-sdk@^1.2.3', '@janua/ui@~1.2.0', '@janua/core@1.2.3']);
});

test('runtime dependency lookup rejects missing, forbidden, outage, malformed and unsatisfied metadata', () => {
  const manifest = { dependencies: { '@janua/typescript-sdk': '^1.2.3' } };
  for (const code of ['E404', 'E403', 'E500']) assert.throws(() => ensurePublishedDependencies(manifest, () => ({ status: 1, stdout: JSON.stringify({ error: { code } }) })), /lookup failed/);
  for (const data of [null, [], {}, '1.2.3', { name: '@other/package', version: '1.2.3' }, { name: '@janua/typescript-sdk', version: '2.0.0' }, { name: '@janua/typescript-sdk', version: 'invalid' }]) assert.throws(() => ensurePublishedDependencies(manifest, () => ({ status: 0, stdout: JSON.stringify(data) })));
  assert.throws(() => ensurePublishedDependencies(manifest, () => ({ status: 0, stdout: 'invalid JSON' })));
  assert.doesNotThrow(() => ensurePublishedDependencies(manifest, () => ({ status: 0, stdout: JSON.stringify([{ name: '@janua/typescript-sdk', version: '1.2.4' }, { name: '@janua/typescript-sdk', version: '1.3.0' }]) })));
  assert.throws(() => ensurePublishedDependencies({ dependencies: { '@janua/core': 'npm:external@1.2.3' } }));
});

test('packed workspace range checks respect caret-zero and prerelease boundaries', () => {
  for (const [version, range, expected] of [
    ['0.1.5', '^0.1.4', true], ['0.2.0', '^0.1.4', false],
    ['0.0.5', '^0.0.4', false], ['0.0.4', '^0.0.4', true],
    ['1.3.0', '~1.2.3', false], ['1.2.9', '~1.2.3', true],
    ['1.2.3-beta.2', '^1.2.3-beta.1', true], ['1.2.3-beta.1', '^1.2.3', false],
    ['1.3.0-beta.1', '^1.2.3-beta.1', false], ['1.3.0', '^1.2.3-beta.1', true],
    ['1.2.3', '*', true], ['1.2.3-beta', '*', false], ['1.2.4', '1.2.3', false],
  ]) assert.equal(satisfiesPublishedRange(version, range), expected, `${version} vs ${range}`);
  assert.throws(() => satisfiesPublishedRange('1.2.3', 'latest'));
});
