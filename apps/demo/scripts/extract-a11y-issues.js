#!/usr/bin/env node

// Extract accessibility issues from Lighthouse JSON reports
const fs = require('fs');
const path = require('path');

const REPORTS_DIR = 'lighthouse-reports';
const files = fs.readdirSync(REPORTS_DIR).filter(f => f.endsWith('.report.json'));

console.log('# Accessibility Analysis\n');

const allIssues = new Map();
let totalPages = 0;
let totalScore = 0;

files.forEach(file => {
  const data = JSON.parse(fs.readFileSync(path.join(REPORTS_DIR, file), 'utf8'));
  const pageName = file.replace('.report.json', '');

  totalPages++;
  totalScore += (data.categories.accessibility?.score || 0) * 100;

  // Extract failed audits
  const audits = data.audits;
  Object.entries(audits).forEach(([key, audit]) => {
    if (audit.score !== null && audit.score < 1 && audit.scoreDisplayMode !== 'informative') {
      if (!allIssues.has(audit.title)) {
        allIssues.set(audit.title, {
          title: audit.title,
          description: audit.description,
          pages: [],
          severity: audit.score === 0 ? 'high' : 'medium'
        });
      }
      allIssues.get(audit.title).pages.push(pageName);
    }
  });
});

console.log(`## Overall Accessibility Score: ${Math.round(totalScore / totalPages)}/100\n`);

if (allIssues.size === 0) {
  console.log('✅ **No critical accessibility issues found!**\n');
} else {
  console.log(`## Issues Found: ${allIssues.size}\n`);

  // Sort by number of affected pages
  const sortedIssues = Array.from(allIssues.values())
    .sort((a, b) => b.pages.length - a.pages.length);

  sortedIssues.forEach(issue => {
    console.log(`### ${issue.severity === 'high' ? '🔴' : '🟡'} ${issue.title}`);
    console.log(`**Affected pages**: ${issue.pages.length}/${totalPages}`);
    console.log(`**Description**: ${issue.description}`);
    console.log('');
  });
}

// WCAG compliance check
console.log('## WCAG 2.1 Compliance\n');
const avgScore = Math.round(totalScore / totalPages);
console.log(`**Level AA Compliance**: ${avgScore >= 90 ? '✅ Pass' : avgScore >= 80 ? '⚠️ Partial' : '❌ Fail'}`);
console.log(`**Score**: ${avgScore}/100 (target: ≥90 for AA)`);
