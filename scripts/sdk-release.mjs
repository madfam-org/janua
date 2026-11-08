/** Canonical NPM release contract. Commands fail closed; no shell interpolation. */
import { appendFileSync, lstatSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

export const REGISTRY = 'https://npm.madfam.io';
export const PACKAGES = Object.freeze({
  'typescript-sdk': '@janua/typescript-sdk', 'react-sdk': '@janua/react-sdk',
  'nextjs-sdk': '@janua/nextjs', 'vue-sdk': '@janua/vue-sdk',
  'react-native-sdk': '@janua/react-native', core: '@janua/core', ui: '@janua/ui',
  'jwt-utils': '@janua/jwt-utils', edge: '@janua/edge', cli: '@janua/cli',
  'feature-flags': '@janua/feature-flags',
});
const SEMVER = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*))?$/;
const DEPENDENCIES = ['dependencies', 'optionalDependencies', 'peerDependencies', 'devDependencies'];

export function validateRelease(root, sdkName, version) {
  if (!Object.hasOwn(PACKAGES, sdkName)) throw new Error('Package directory is not allowlisted');
  if (typeof version !== 'string' || !SEMVER.test(version)) throw new Error('Version must be release semver without build metadata');
  const directory = join(root, 'packages', sdkName);
  const manifest = JSON.parse(readFileSync(join(directory, 'package.json'), 'utf8'));
  if (manifest.private === true || manifest.name !== PACKAGES[sdkName]) throw new Error('Package identity is not publishable');
  if (manifest.version !== version) throw new Error('Requested version does not match package.json');
  if (manifest.publishConfig?.registry && manifest.publishConfig.registry.replace(/\/$/, '') !== REGISTRY) throw new Error('Unexpected publish registry');
  if (manifest.publishConfig?.access && manifest.publishConfig.access !== 'restricted') throw new Error('Unexpected publish access');
  if (manifest.publishConfig?.tag && manifest.publishConfig.tag !== (version.includes('-') ? 'next' : 'latest')) throw new Error('Unexpected publish tag');
  return { sdkName, packageName: manifest.name, version, directory, releaseTag: `${sdkName}-v${version}`, prerelease: version.includes('-'), distTag: version.includes('-') ? 'next' : 'latest' };
}

export function resolveRequest(root, env) {
  if (env.GITHUB_EVENT_NAME === 'workflow_dispatch') return validateRelease(root, env.SDK_NAME, env.SDK_VERSION);
  if (env.GITHUB_EVENT_NAME !== 'push' || !env.GITHUB_REF?.startsWith('refs/tags/')) throw new Error('Expected package tag or explicit workflow dispatch');
  const tag = env.GITHUB_REF.slice('refs/tags/'.length);
  const sdkName = Object.keys(PACKAGES).find(name => tag.startsWith(`${name}-v`));
  if (!sdkName) throw new Error('Tag does not identify an allowlisted NPM package');
  return validateRelease(root, sdkName, tag.slice(sdkName.length + 2));
}

export function command(binary, args, options = {}) {
  const result = spawnSync(binary, args, { encoding: 'utf8', maxBuffer: 16 * 1024 * 1024, ...options });
  if (result.error) throw new Error(`Unable to execute ${binary}`);
  return result;
}
function checked(binary, args, options, run) {
  const result = run(binary, args, options);
  if (result.status !== 0) throw new Error(`${binary} failed (exit ${result.status})`);
  return result.stdout;
}

/** Only npm's structured E404 means absent; auth/network/parse failures block. */
export function assertRegistryAbsent(result, expectedVersion) {
  if (result.status === 0) {
    let version;
    try { version = JSON.parse(result.stdout); } catch { throw new Error('Registry returned invalid version metadata'); }
    if (version !== expectedVersion) throw new Error('Registry returned unexpected version metadata');
    throw new Error('Version already published; prepare a new version instead');
  }
  if (!Number.isInteger(result.status) || result.status < 1) throw new Error('Registry lookup did not complete');
  let error;
  try { error = JSON.parse(result.stdout || result.stderr); } catch { throw new Error('Registry lookup failed without structured E404'); }
  if (error?.error?.code !== 'E404') throw new Error('Registry lookup failed; absence is not established');
}
export function ensureUnpublished(release, run = command) {
  const result = run('npm', ['view', `${release.packageName}@${release.version}`, 'version', '--json', '--registry', REGISTRY]);
  assertRegistryAbsent(result, release.version);
}

/** Existing annotated and lightweight release tags must identify this checkout. */
export function ensureReleaseTag(release, run = command) {
  const head = checked('git', ['rev-parse', 'HEAD'], {}, run).trim();
  if (!/^[0-9a-f]{40,64}$/.test(head)) throw new Error('Cannot establish release commit');
  const ref = `refs/tags/${release.releaseTag}`;
  const result = checked('git', ['ls-remote', '--tags', 'origin', ref, `${ref}^{}`], {}, run).trim();
  if (!result) return;
  const refs = new Map();
  for (const line of result.split('\n')) {
    const [sha, name, extra] = line.split(/\s+/);
    if (extra || !/^[0-9a-f]{40,64}$/.test(sha) || ![ref, `${ref}^{}`].includes(name) || refs.has(name)) throw new Error('Unexpected remote release tag metadata');
    refs.set(name, sha);
  }
  if (!refs.has(ref) || (refs.get(`${ref}^{}`) || refs.get(ref)) !== head) throw new Error('Existing release tag does not point to this checkout');
}

function parseVersion(version) {
  const match = typeof version === 'string' && version.match(SEMVER);
  if (!match) throw new Error('Invalid registry dependency version');
  return { core: match.slice(1, 4).map(BigInt), pre: match[4]?.split('.') || [] };
}
function compareVersions(a, b) {
  for (let i = 0; i < 3; i++) if (a.core[i] !== b.core[i]) return a.core[i] < b.core[i] ? -1 : 1;
  if (!a.pre.length || !b.pre.length) return a.pre.length === b.pre.length ? 0 : a.pre.length ? -1 : 1;
  for (let i = 0; i < Math.max(a.pre.length, b.pre.length); i++) {
    if (a.pre[i] === undefined || b.pre[i] === undefined) return a.pre[i] === b.pre[i] ? 0 : a.pre[i] === undefined ? -1 : 1;
    if (a.pre[i] === b.pre[i]) continue;
    const numericA = /^\d+$/.test(a.pre[i]), numericB = /^\d+$/.test(b.pre[i]);
    if (numericA && numericB) return BigInt(a.pre[i]) < BigInt(b.pre[i]) ? -1 : 1;
    if (numericA !== numericB) return numericA ? -1 : 1;
    return a.pre[i] < b.pre[i] ? -1 : 1;
  }
  return 0;
}
/** Packed workspace ranges are exact/^/~. Reject unsupported ranges, not guess. */
export function satisfiesPublishedRange(version, range) {
  const actual = parseVersion(version);
  if (range === '*') return actual.pre.length === 0;
  const prefix = ['^', '~'].includes(range[0]) ? range[0] : '';
  const minimum = parseVersion(prefix ? range.slice(1) : range);
  if (!prefix) return compareVersions(actual, minimum) === 0;
  if (actual.pre.length && (!minimum.pre.length || actual.core.some((value, i) => value !== minimum.core[i]))) return false;
  const upper = { core: [...minimum.core], pre: [] };
  const index = prefix === '~' ? 1 : minimum.core[0] > 0n ? 0 : minimum.core[1] > 0n ? 1 : 2;
  upper.core[index]++;
  for (let i = index + 1; i < 3; i++) upper.core[i] = 0n;
  return compareVersions(actual, minimum) >= 0 && compareVersions(actual, upper) < 0;
}
export function ensurePublishedDependencies(manifest, run = command) {
  const checkedDependencies = new Set();
  for (const section of ['dependencies', 'optionalDependencies']) {
    for (const [key, spec] of Object.entries(manifest[section] || {})) {
      let name = key, range = spec;
      if (spec.startsWith('npm:')) {
        const alias = spec.match(/^npm:((?:@[^/]+\/)?[^@]+)@(.+)$/);
        if (!alias) throw new Error('Invalid runtime dependency alias');
        [, name, range] = alias;
      }
      if (!name.startsWith('@janua/')) {
        if (key.startsWith('@janua/')) throw new Error('Internal runtime dependency aliases an external package');
        continue;
      }
      if (!/^@janua\/[a-z0-9][a-z0-9._-]*$/.test(name)) throw new Error('Invalid internal runtime dependency name');
      // Validate the supported range before passing it to the registry query.
      satisfiesPublishedRange('0.0.0', range);
      const query = `${name}@${range}`;
      if (checkedDependencies.has(query)) continue;
      checkedDependencies.add(query);
      const result = run('npm', ['view', query, '--json', '--registry', REGISTRY]);
      if (result.status !== 0) throw new Error(`Registry lookup failed for internal runtime dependency ${name}`);
      let data;
      try { data = JSON.parse(result.stdout); } catch { throw new Error('Invalid dependency registry metadata'); }
      const versions = Array.isArray(data) ? data : [data];
      if (!versions.length || versions.some(value => !value || value.name !== name || typeof value.version !== 'string') || !versions.some(value => satisfiesPublishedRange(value.version, range))) throw new Error(`No published version satisfies internal runtime dependency ${name}`);
    }
  }
}

export function inspectManifest(manifest, release, files) {
  if (manifest.name !== release.packageName || manifest.version !== release.version || manifest.private === true) throw new Error('Packed package identity differs from the validated release');
  if (manifest.publishConfig?.registry && manifest.publishConfig.registry.replace(/\/$/, '') !== REGISTRY) throw new Error('Packed registry override is not allowed');
  if (manifest.publishConfig?.access && manifest.publishConfig.access !== 'restricted') throw new Error('Packed access override is not allowed');
  if (manifest.publishConfig?.tag && manifest.publishConfig.tag !== release.distTag) throw new Error('Packed tag override is not allowed');
  for (const section of DEPENDENCIES) {
    for (const value of Object.values(manifest[section] || {})) {
      if (typeof value !== 'string' || /workspace:|^(?:file:|link:|\.\.?\/)/.test(value)) throw new Error(`Packed ${section} contains an unpublished local dependency`);
    }
  }
  const paths = [];
  const collect = value => {
    if (typeof value === 'string') paths.push(value);
    else if (value && typeof value === 'object') Object.values(value).forEach(collect);
  };
  ['main', 'module', 'types', 'typings', 'bin', 'exports'].forEach(key => collect(manifest[key]));
  for (const entry of paths) {
    const path = entry.replace(/^\.\//, '');
    if (path.startsWith('/') || path.split('/').includes('..')) throw new Error('Packed entrypoint escapes package');
    // Export patterns are allowed, but at least one packaged file must match.
    const pattern = new RegExp(`^package/${path.split('*').map(part => part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*')}$`);
    if (![...files].some(file => pattern.test(file))) throw new Error(`Packed entrypoint is missing: ${entry}`);
  }
}
function inspectTarball(tarball, release, run) {
  const manifest = JSON.parse(checked('tar', ['-xOf', tarball, 'package/package.json'], {}, run));
  const files = new Set(checked('tar', ['-tzf', tarball], {}, run).trim().split('\n'));
  inspectManifest(manifest, release, files);
  return manifest;
}
const digest = path => createHash('sha512').update(readFileSync(path)).digest('hex');

export function packRelease(release, run = command) {
  const output = mkdtempSync(join(tmpdir(), 'janua-sdk-release-'));
  const tarball = join(output, 'package.tgz');
  try {
    checked('pnpm', ['--dir', release.directory, 'pack', '--out', tarball], {}, run);
    inspectTarball(tarball, release, run);
    const metadata = join(output, 'release.json');
    writeFileSync(metadata, JSON.stringify({ packageName: release.packageName, version: release.version, tarball, sha512: digest(tarball) }));
    return metadata;
  } catch (error) {
    rmSync(output, { recursive: true, force: true });
    throw error;
  }
}

/** Publish exactly the inspected tarball; never rerun package lifecycle scripts. */
export function publishRelease(release, metadataPath, run = command) {
  const metadata = JSON.parse(readFileSync(metadataPath, 'utf8'));
  const tarball = join(dirname(resolve(metadataPath)), 'package.tgz');
  if (metadata.packageName !== release.packageName || metadata.version !== release.version || metadata.tarball !== tarball || !lstatSync(tarball).isFile() || metadata.sha512 !== digest(tarball)) throw new Error('Packed release changed after inspection');
  const manifest = inspectTarball(tarball, release, run);
  ensureReleaseTag(release, run);
  ensureUnpublished(release, run);
  ensurePublishedDependencies(manifest, run);
  checked('npm', ['publish', tarball, '--ignore-scripts', '--registry', REGISTRY, '--access', 'restricted', '--tag', release.distTag], {}, run);
}
function output(values) {
  if (!process.env.GITHUB_OUTPUT) throw new Error('GITHUB_OUTPUT is required');
  for (const [key, value] of Object.entries(values)) {
    if (String(value).includes('\n') || String(value).includes('\r')) throw new Error('Invalid multiline output');
    appendFileSync(process.env.GITHUB_OUTPUT, `${key}=${value}\n`);
  }
}
export function main(mode, env = process.env, root = process.cwd()) {
  const release = mode === 'validate' ? resolveRequest(root, env) : validateRelease(root, env.SDK_NAME, env.SDK_VERSION);
  if (mode === 'validate') output({ sdk_name: release.sdkName, package_name: release.packageName, version: release.version, release_tag: release.releaseTag, prerelease: release.prerelease });
  else if (mode === 'registry') { ensureReleaseTag(release); ensureUnpublished(release); }
  else if (mode === 'pack') output({ release_manifest: packRelease(release) });
  else if (mode === 'publish') publishRelease(release, env.RELEASE_MANIFEST);
  else throw new Error('Unknown release command');
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { main(process.argv[2]); }
  catch (error) { console.error(error instanceof Error ? error.message : 'Release validation failed'); process.exitCode = 1; }
}
