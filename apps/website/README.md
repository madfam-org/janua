# Janua Website

> **Public marketing site** for the Janua identity platform

**Status:** Production · **Domain:** `janua.dev` · **Port:** `3000` (`@janua/website`)

## Overview

The Janua website is the public landing experience: product positioning, pricing, legal pages, interactive demo, and developer resources. Built with Next.js 15, Tailwind CSS v4, and the shared `@janua/ui` design system.

## Quick start

```bash
# From monorepo root
pnpm install

# Website dev server
pnpm --filter @janua/website dev
```

Site: [http://localhost:3000](http://localhost:3000)

### Environment

Copy `apps/website/.env.example` to `.env.local`. Key variables:

```env
NEXT_PUBLIC_APP_URL=http://localhost:3000
NEXT_PUBLIC_POSTHOG_KEY=   # optional analytics
```

## Routes (marketing)

| Path | Purpose |
|------|---------|
| `/` | Home |
| `/pricing` | Plans |
| `/demo` | Interactive auth demo |
| `/legal/privacy`, `/legal/terms`, `/legal/cookies` | Legal |
| `/deploy/enclii` | Enclii co-marketing deploy guide |

Full pipeline docs: [docs/runbooks/production-gitops-reconcile.md](../../docs/runbooks/production-gitops-reconcile.md)

---

## Legacy reference

The sections below describe an older marketing app layout (`apps/marketing`, port 3003). The canonical app is `apps/website` on port 3000.

## Features

### Project Structure

```
apps/marketing/
├── app/                    # Next.js 14 App Router
│   ├── (marketing)/       # Marketing pages
│   │   ├── page.tsx       # Homepage
│   │   ├── pricing/       # Pricing page
│   │   ├── features/      # Features showcase
│   │   ├── about/         # About page
│   │   ├── blog/          # Blog posts
│   │   ├── changelog/     # Product updates
│   │   └── contact/       # Contact form
│   ├── (legal)/          # Legal pages
│   │   ├── privacy/      # Privacy policy
│   │   ├── terms/        # Terms of service
│   │   └── security/     # Security info
│   ├── api/              # API routes
│   └── layout.tsx        # Root layout
├── components/           # React components
│   ├── marketing/       # Marketing components
│   ├── hero/           # Hero sections
│   ├── features/       # Feature showcases
│   ├── pricing/        # Pricing components
│   ├── testimonials/   # Customer testimonials
│   └── three/          # 3D components
├── lib/                # Utilities
│   ├── animations/     # Animation configs
│   ├── three/         # Three.js utilities
│   └── mdx/           # MDX configuration
├── content/           # Content files
│   ├── blog/         # Blog posts (MDX)
│   ├── changelog/    # Updates (MDX)
│   └── features/     # Feature data
├── public/           # Static assets
│   ├── images/      # Images
│   ├── models/      # 3D models
│   └── videos/      # Video assets
└── styles/          # Styles
```

### Technology Stack

- **Framework:** Next.js 14 (App Router)
- **3D Graphics:** Three.js + React Three Fiber
- **Animations:** Framer Motion + Lottie
- **Content:** MDX for blog/documentation
- **Styling:** Tailwind CSS + CSS Modules
- **UI Components:** @janua/ui design system
- **Analytics:** PostHog, Google Analytics, Clarity

## 🎨 Features

### Homepage Components

#### 🚀 Hero Section
```tsx
// Interactive 3D hero with scroll animations
<HeroSection>
  <Canvas>
    <JanuaLogo3D />
    <OrbitControls />
  </Canvas>
  <HeroContent />
</HeroSection>
```

#### ✨ Feature Showcases
- Interactive feature cards
- Animated demonstrations
- Code examples
- Video walkthroughs

#### 💬 Social Proof
- Customer testimonials
- Logo carousel
- Case studies
- Trust badges

#### 📊 Stats Section
- Live platform statistics
- Growth metrics
- Performance benchmarks

### Content Management

#### Blog System
```tsx
// MDX-powered blog with syntax highlighting
export default function BlogPost({ params }) {
  const post = await getPost(params.slug);
  return <MDXRemote source={post.content} />;
}
```

#### Changelog
- Product updates
- Feature announcements
- Breaking changes
- Migration guides

## 🎭 3D Graphics

### Three.js Integration

```tsx
// components/three/AnimatedLogo.tsx
import { Canvas, useFrame } from '@react-three/fiber';
import { useGLTF } from '@react-three/drei';

export function AnimatedLogo() {
  const { scene } = useGLTF('/models/janua-logo.glb');
  
  useFrame((state) => {
    scene.rotation.y = Math.sin(state.clock.elapsedTime) * 0.3;
  });
  
  return <primitive object={scene} />;
}
```

### Performance Optimization

- Lazy loading for 3D components
- LOD (Level of Detail) for models
- Texture compression
- GPU optimization
- Fallback for low-end devices

## 🚀 Performance

### Optimization Strategies

#### Image Optimization
```tsx
import Image from 'next/image';

// Automatic optimization with Next.js
<Image
  src="/hero-image.png"
  alt="Janua Platform"
  width={1200}
  height={600}
  priority
  placeholder="blur"
/>
```

#### Code Splitting
- Route-based splitting
- Component lazy loading
- Dynamic imports for heavy libraries

#### SEO Optimization
```tsx
// app/layout.tsx
export const metadata = {
  title: 'Janua - Secure Identity Platform',
  description: 'Unify auth, orgs, and policy with edge-fast verification',
  openGraph: {
    images: ['/og-image.png'],
  },
};
```

### Performance Metrics

Target metrics:
- **LCP:** < 2.5s
- **FID:** < 100ms
- **CLS:** < 0.1
- **TTI:** < 3.5s
- **Lighthouse Score:** 95+

## 📈 Analytics & Tracking

### Conversion Tracking

```tsx
// lib/analytics.ts
export function trackEvent(event: string, properties?: any) {
  // PostHog
  posthog.capture(event, properties);
  
  // Google Analytics
  gtag('event', event, properties);
  
  // Custom tracking
  fetch('/api/track', {
    method: 'POST',
    body: JSON.stringify({ event, properties }),
  });
}
```

### A/B Testing

```tsx
// Using PostHog feature flags
const variant = useFeatureFlag('hero-variant');

return variant === 'b' ? <HeroVariantB /> : <HeroVariantA />;
```

## 🎯 Conversion Optimization

### Call-to-Action Strategy

- Primary CTA: "Start Free Trial"
- Secondary CTA: "Book Demo"
- Tertiary: "View Documentation"

### Landing Page Templates

```
/templates/
├── webinar/          # Webinar registration
├── ebook/           # eBook download
├── demo/            # Demo request
└── trial/           # Trial signup
```

## 📝 Content Management

### Blog Writing

```markdown
---
title: "Introduction to Janua"
date: "2024-01-15"
author: "Team Janua"
category: "Product"
tags: ["authentication", "security"]
---

Blog content in MDX format...
```

### SEO Content

- Programmatic SEO pages
- Comparison pages
- Alternative pages
- Use case pages
- Integration pages

## 🧪 Testing

### Testing Strategy

```bash
# Component tests
yarn test

# Visual regression tests
yarn test:visual

# Performance tests
yarn test:performance

# SEO tests
yarn test:seo
```

## 🚢 Deployment

### Production Build

```bash
# Build for production
yarn build

# Analyze bundle
yarn analyze

# Start production server
yarn start
```

### Vercel Configuration

```json
// vercel.json
{
  "functions": {
    "app/api/*": {
      "maxDuration": 10
    }
  },
  "redirects": [
    {
      "source": "/docs",
      "destination": "https://docs.janua.dev",
      "permanent": false
    }
  ]
}
```

## 🎨 Design System

### Brand Colors

```css
:root {
  --janua-primary: #6366f1;
  --janua-secondary: #8b5cf6;
  --janua-accent: #ec4899;
  --janua-dark: #1e293b;
  --janua-light: #f8fafc;
}
```

### Typography

- **Headings:** Inter
- **Body:** Inter
- **Code:** JetBrains Mono

## 🔍 SEO

### Technical SEO

- XML sitemap generation
- Robots.txt configuration
- Canonical URLs
- Structured data (JSON-LD)
- Open Graph tags
- Twitter Cards

### Content SEO

- Keyword optimization
- Meta descriptions
- Header hierarchy
- Internal linking
- Image alt texts

## 📊 Monitoring

### Analytics Dashboard

Tracking:
- Page views and unique visitors
- Conversion rates
- Bounce rates
- User flow
- Campaign performance

### Error Monitoring

- Sentry for error tracking
- Custom error boundaries
- Performance monitoring
- Uptime monitoring

## 🛠️ Development

### Local Development

```bash
# Start dev server
yarn dev

# Format code
yarn format

# Lint code
yarn lint

# Type check
yarn typecheck
```

### Content Workflow

1. Write content in MDX
2. Preview locally
3. Submit PR for review
4. Auto-deploy on merge

## 📚 Resources

- [Next.js Docs](https://nextjs.org/docs)
- [Three.js](https://threejs.org)
- [React Three Fiber](https://docs.pmnd.rs/react-three-fiber)
- [Framer Motion](https://www.framer.com/motion)
- [MDX](https://mdxjs.com)

## 🤝 Contributing

See [Contributing Guide](../../CONTRIBUTING.md) for guidelines.

## 📄 License

Part of the Janua platform. See [LICENSE](../../LICENSE) in the root directory.