#!/usr/bin/env node

// Extract key metrics from Lighthouse JSON reports
const fs = require('fs');
const path = require('path');

const REPORTS_DIR = 'lighthouse-reports';
const files = fs.readdirSync(REPORTS_DIR).filter(f => f.endsWith('.report.json'));

console.log('# Lighthouse Performance Report\n');
console.log('| Page | Performance | Accessibility | Best Practices | SEO | FCP | LCP | TBT | CLS | SI |');
console.log('|------|------------|---------------|----------------|-----|-----|-----|-----|-----|-----|');

const metrics = [];

files.forEach(file => {
  const data = JSON.parse(fs.readFileSync(path.join(REPORTS_DIR, file), 'utf8'));
  const pageName = file.replace('.report.json', '').replace(/-/g, '/').replace('/', '');

  const categories = data.categories;
  const audits = data.audits;

  const perf = Math.round((categories.performance?.score || 0) * 100);
  const a11y = Math.round((categories.accessibility?.score || 0) * 100);
  const bp = Math.round((categories['best-practices']?.score || 0) * 100);
  const seo = Math.round((categories.seo?.score || 0) * 100);

  const fcp = audits['first-contentful-paint']?.displayValue || 'N/A';
  const lcp = audits['largest-contentful-paint']?.displayValue || 'N/A';
  const tbt = audits['total-blocking-time']?.displayValue || 'N/A';
  const cls = audits['cumulative-layout-shift']?.displayValue || 'N/A';
  const si = audits['speed-index']?.displayValue || 'N/A';

  console.log(`| /${pageName} | ${perf} | ${a11y} | ${bp} | ${seo} | ${fcp} | ${lcp} | ${tbt} | ${cls} | ${si} |`);

  metrics.push({
    page: `/${pageName}`,
    performance: perf,
    accessibility: a11y,
    bestPractices: bp,
    seo: seo,
    fcp: audits['first-contentful-paint']?.numericValue || 0,
    lcp: audits['largest-contentful-paint']?.numericValue || 0,
    tbt: audits['total-blocking-time']?.numericValue || 0,
    cls: audits['cumulative-layout-shift']?.numericValue || 0,
    si: audits['speed-index']?.numericValue || 0,
  });
});

// Calculate averages
console.log('\n## Summary Statistics\n');
const avgPerf = Math.round(metrics.reduce((sum, m) => sum + m.performance, 0) / metrics.length);
const avgA11y = Math.round(metrics.reduce((sum, m) => sum + m.accessibility, 0) / metrics.length);
const avgBP = Math.round(metrics.reduce((sum, m) => sum + m.bestPractices, 0) / metrics.length);
const avgSEO = Math.round(metrics.reduce((sum, m) => sum + m.seo, 0) / metrics.length);

console.log(`**Average Scores**:`);
console.log(`- Performance: ${avgPerf}/100`);
console.log(`- Accessibility: ${avgA11y}/100`);
console.log(`- Best Practices: ${avgBP}/100`);
console.log(`- SEO: ${avgSEO}/100`);

console.log('\n**Core Web Vitals**:');
const avgFCP = Math.round(metrics.reduce((sum, m) => sum + m.fcp, 0) / metrics.length);
const avgLCP = Math.round(metrics.reduce((sum, m) => sum + m.lcp, 0) / metrics.length);
const avgTBT = Math.round(metrics.reduce((sum, m) => sum + m.tbt, 0) / metrics.length);
const avgCLS = (metrics.reduce((sum, m) => sum + m.cls, 0) / metrics.length).toFixed(3);
const avgSI = Math.round(metrics.reduce((sum, m) => sum + m.si, 0) / metrics.length);

console.log(`- First Contentful Paint (FCP): ${avgFCP}ms`);
console.log(`- Largest Contentful Paint (LCP): ${avgLCP}ms`);
console.log(`- Total Blocking Time (TBT): ${avgTBT}ms`);
console.log(`- Cumulative Layout Shift (CLS): ${avgCLS}`);
console.log(`- Speed Index (SI): ${avgSI}ms`);

// Performance ratings
console.log('\n**Performance Ratings**:');
console.log(`- FCP: ${avgFCP < 1800 ? '✅ Good' : avgFCP < 3000 ? '⚠️ Needs Improvement' : '❌ Poor'} (target: <1.8s)`);
console.log(`- LCP: ${avgLCP < 2500 ? '✅ Good' : avgLCP < 4000 ? '⚠️ Needs Improvement' : '❌ Poor'} (target: <2.5s)`);
console.log(`- TBT: ${avgTBT < 200 ? '✅ Good' : avgTBT < 600 ? '⚠️ Needs Improvement' : '❌ Poor'} (target: <200ms)`);
console.log(`- CLS: ${avgCLS < 0.1 ? '✅ Good' : avgCLS < 0.25 ? '⚠️ Needs Improvement' : '❌ Poor'} (target: <0.1)`);

// Showcase-specific analysis
console.log('\n## Showcase Pages Performance\n');
const showcases = metrics.filter(m => m.page.includes('showcase'));
const avgShowcasePerf = Math.round(showcases.reduce((sum, m) => sum + m.performance, 0) / showcases.length);
const avgShowcaseLCP = Math.round(showcases.reduce((sum, m) => sum + m.lcp, 0) / showcases.length);

console.log(`**9 Showcase Pages** (signin, signup, user-profile, password-reset, verification, mfa, security, organization, compliance):`);
console.log(`- Average Performance Score: ${avgShowcasePerf}/100`);
console.log(`- Average LCP: ${avgShowcaseLCP}ms`);
console.log(`- Bundle Consistency: ${showcases.every(s => s.performance >= avgShowcasePerf - 5) ? '✅ Excellent' : '⚠️ Variable'}`);
