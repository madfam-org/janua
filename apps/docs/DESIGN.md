# Plinto Documentation Site Design

## Overview
docs.plinto.dev - A modern, developer-focused documentation site for the Plinto identity platform

## Design Principles
1. **Developer-First**: Optimized for developers with code examples, API references, and interactive playgrounds
2. **Fast Navigation**: Quick access to any documentation page within 2 clicks
3. **Search-Centric**: Powerful search with instant results and keyboard navigation
4. **Interactive Learning**: Live code examples and API playground
5. **Responsive & Accessible**: Works on all devices, WCAG 2.1 AA compliant

## Information Architecture

```
docs.plinto.dev/
├── Getting Started
│   ├── Quick Start
│   ├── Installation
│   ├── Authentication Basics
│   └── First App Tutorial
├── Guides
│   ├── Authentication
│   │   ├── Email/Password
│   │   ├── Passkeys/WebAuthn
│   │   ├── Social Login
│   │   └── Multi-Factor Auth
│   ├── Organizations
│   │   ├── Creating Organizations
│   │   ├── RBAC & Permissions
│   │   └── Invitations
│   ├── Sessions
│   │   ├── Session Management
│   │   ├── Token Refresh
│   │   └── Device Management
│   └── Security
│       ├── Best Practices
│       ├── Rate Limiting
│       └── Audit Logs
├── API Reference
│   ├── Authentication
│   ├── Users
│   ├── Organizations
│   ├── Sessions
│   ├── Webhooks
│   └── Admin
├── SDKs
│   ├── JavaScript/TypeScript
│   │   ├── @plinto/nextjs
│   │   ├── @plinto/react-sdk
│   │   ├── @plinto/node
│   │   └── @plinto/edge
│   ├── Python
│   ├── Go
│   └── Ruby
├── Examples
│   ├── Next.js App Router
│   ├── Next.js Pages Router
│   ├── React SPA
│   ├── Node.js Backend
│   └── Edge Functions
└── Resources
    ├── Changelog
    ├── Migration Guides
    ├── Troubleshooting
    └── Support

```

## Visual Design

### Color Palette (extends Plinto theme)
```typescript
const docsTheme = {
  ...plintoTheme,
  colors: {
    ...plintoTheme.colors,
    // Docs-specific
    codeBackground: '#1e293b',     // slate-800
    codeText: '#e2e8f0',           // slate-200
    syntaxKeyword: '#60a5fa',     // blue-400
    syntaxString: '#34d399',      // emerald-400
    syntaxComment: '#94a3b8',     // slate-400
    warning: '#fbbf24',            // amber-400
    tip: '#10b981',                // emerald-500
    note: '#3b82f6',               // blue-500
  }
}
```

### Typography
- **Headings**: Inter (600-700 weight)
- **Body**: Inter (400 weight)
- **Code**: JetBrains Mono

### Layout Components

#### 1. Header/Navigation
```
┌─────────────────────────────────────────────────────────────┐
│ [Logo] Plinto Docs    [Search...]    [v1.0] [GitHub] [Dark] │
├─────────────────────────────────────────────────────────────┤
│ Getting Started │ Guides │ API Reference │ SDKs │ Examples  │
└─────────────────────────────────────────────────────────────┘
```

#### 2. Three-Column Layout
```
┌──────────┬─────────────────────────────┬──────────┐
│ Sidebar  │      Main Content           │ On Page  │
│          │                             │   TOC    │
│ - Item 1 │  # Page Title              │          │
│ - Item 2 │                             │ - Intro  │
│   - 2.1  │  Content here...            │ - Setup  │
│   - 2.2  │                             │ - Usage  │
│ - Item 3 │  [Code Example]             │ - API    │
│          │                             │          │
└──────────┴─────────────────────────────┴──────────┘
```

## Component Library

### 1. CodeBlock
```tsx
interface CodeBlockProps {
  language: 'typescript' | 'javascript' | 'python' | 'bash' | 'json'
  title?: string
  showLineNumbers?: boolean
  highlightLines?: number[]
  copyButton?: boolean
  runnable?: boolean
}
```

### 2. APIEndpoint
```tsx
interface APIEndpointProps {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
  path: string
  description: string
  parameters?: Parameter[]
  requestBody?: Schema
  responses?: Response[]
  example?: CodeExample
}
```

### 3. InteractiveExample
```tsx
interface InteractiveExampleProps {
  title: string
  description: string
  code: string
  editable?: boolean
  output?: 'console' | 'preview' | 'both'
  dependencies?: string[]
}
```

### 4. VersionSelector
```tsx
interface VersionSelectorProps {
  currentVersion: string
  availableVersions: Version[]
  onChange: (version: string) => void
}
```

### 5. SearchModal
```tsx
interface SearchModalProps {
  isOpen: boolean
  onClose: () => void
  onSelect: (result: SearchResult) => void
}
```

### 6. Callout
```tsx
interface CalloutProps {
  type: 'note' | 'tip' | 'warning' | 'danger'
  title?: string
  children: React.ReactNode
}
```

### 7. TabGroup
```tsx
interface TabGroupProps {
  tabs: Array<{
    label: string
    value: string
    content: React.ReactNode
  }>
  defaultTab?: string
}
```

### 8. ParameterTable
```tsx
interface ParameterTableProps {
  parameters: Array<{
    name: string
    type: string
    required: boolean
    description: string
    default?: string
  }>
}
```

## Key Features

### 1. Instant Search
- Algolia-powered search with < 50ms response time
- Keyboard navigation (⌘K to open)
- Search results show context and highlights
- Filter by type (guides, API, examples)

### 2. Code Examples
- Syntax highlighting with Prism.js
- Copy button on all code blocks
- Language selector for multi-language examples
- Live editing in playground mode

### 3. API Playground
- Interactive API testing interface
- Pre-configured with demo credentials
- Request/response inspector
- cURL command generation

### 4. Version Management
- Version selector in header
- Version-specific documentation
- Migration guides between versions
- Deprecation warnings

### 5. Dark Mode
- System preference detection
- Manual toggle
- Persisted preference
- Optimized color schemes for both modes

### 6. Mobile Experience
- Collapsible navigation
- Touch-optimized interactions
- Offline-capable with service worker
- Progressive Web App (PWA) support

## Technical Implementation

### Stack
- **Framework**: Next.js 14 with App Router
- **Styling**: Tailwind CSS + @plinto/ui components
- **Content**: MDX for rich documentation
- **Search**: Algolia DocSearch
- **Code Highlighting**: Prism.js with custom theme
- **Analytics**: Plausible or PostHog
- **Deployment**: Vercel with ISR

### Performance Targets
- **First Contentful Paint**: < 1.2s
- **Time to Interactive**: < 2.5s
- **Search Results**: < 50ms
- **Page Navigation**: < 200ms (with prefetching)

### SEO & Meta
- OpenGraph tags for social sharing
- Structured data for search engines
- Sitemap generation
- Canonical URLs for version management

### Accessibility
- WCAG 2.1 AA compliance
- Keyboard navigation throughout
- Screen reader optimized
- Focus management
- Skip navigation links

## Content Management

### MDX Structure
```mdx
---
title: "Authentication Guide"
description: "Learn how to implement authentication"
category: "guides"
tags: ["auth", "security"]
---

import { Callout, CodeBlock, TabGroup } from '@/components/docs'

# Authentication Guide

<Callout type="tip">
  Passkeys provide the best user experience
</Callout>

<TabGroup tabs={[
  { label: 'Next.js', value: 'nextjs', content: <NextExample /> },
  { label: 'React', value: 'react', content: <ReactExample /> }
]} />
```

### API Documentation Generation
- OpenAPI spec auto-generation from FastAPI
- TypeScript types from OpenAPI
- Automatic SDK documentation

## Navigation Patterns

### Breadcrumbs
```
Docs > Guides > Authentication > Passkeys
```

### Previous/Next Navigation
```
← Previous: Email/Password    |    Next: Social Login →
```

### Related Content
- Automatic suggestions based on current page
- "See also" sections
- Cross-references in content

## Responsive Breakpoints
- **Mobile**: 0-768px (single column, collapsible nav)
- **Tablet**: 768-1024px (two columns)
- **Desktop**: 1024px+ (three columns with TOC)

## Interaction States
- **Hover**: Subtle background change, underline links
- **Focus**: Clear focus ring (brand color)
- **Active**: Pressed state with slight scale
- **Loading**: Skeleton screens for content
- **Error**: Clear error messages with recovery actions

## Special Pages

### 1. Homepage
- Hero with quick start CTA
- Feature grid
- Popular guides
- Latest updates

### 2. API Reference
- Endpoint grouping by resource
- Request/response examples
- Authentication requirements
- Rate limit information

### 3. SDK Pages
- Installation instructions
- Quick start code
- Configuration options
- Method reference

### 4. 404 Page
- Search suggestion
- Popular pages
- Contact support link

## Deployment Configuration

### Environment Variables
```env
NEXT_PUBLIC_DOCS_URL=https://docs.plinto.dev
NEXT_PUBLIC_API_URL=https://api.plinto.dev
NEXT_PUBLIC_ALGOLIA_APP_ID=xxx
NEXT_PUBLIC_ALGOLIA_API_KEY=xxx
NEXT_PUBLIC_ALGOLIA_INDEX=plinto-docs
```

### Build Configuration
```javascript
// next.config.js
module.exports = {
  basePath: '',
  images: {
    domains: ['plinto.dev', 'github.com'],
  },
  async redirects() {
    return [
      {
        source: '/docs',
        destination: '/',
        permanent: true,
      },
    ]
  },
}
```

## Analytics & Monitoring

### Tracked Metrics
- Page views and unique visitors
- Search queries and click-through
- Time on page
- Navigation patterns
- 404 errors
- Code copy events

### Performance Monitoring
- Core Web Vitals
- API response times
- Search performance
- Error rates

## Future Enhancements
1. AI-powered search and Q&A
2. Video tutorials
3. Interactive API explorer
4. Community contributions
5. Localization (i18n)
6. Offline documentation app