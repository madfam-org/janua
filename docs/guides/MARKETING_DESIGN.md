# Plinto Marketing Site Design

## Overview

The Plinto marketing site serves as the primary entry point for developers discovering our identity platform. It must communicate our technical superiority, demonstrate ease of integration, and drive conversions through a compelling developer experience.

**Core Value Proposition**: "The secure substrate for identity — Edge-fast verification with full control"

---

## Site Architecture

### URL Structure (Single Domain)

```
plinto.dev/                     # Landing page
plinto.dev/pricing              # Pricing & plans
plinto.dev/developers           # Developer hub
plinto.dev/playground           # Interactive demo
plinto.dev/customers            # Case studies
plinto.dev/compare/clerk        # Comparison pages
plinto.dev/blog                 # Engineering blog
plinto.dev/docs                 # Documentation
plinto.dev/admin                # Admin panel (gated)
plinto.dev/api/v1/*            # API endpoints
```

### Technical Stack

- **Framework**: Next.js 14 with App Router
- **Styling**: Tailwind CSS + Radix UI
- **Animations**: Framer Motion
- **Analytics**: Plausible (privacy-first)
- **CMS**: MDX for blog/docs
- **Deployment**: Vercel Edge Functions

---

## Landing Page Structure

### 1. Hero Section

```typescript
interface HeroSection {
  headline: "Identity infrastructure that moves at the speed of your users"
  subheadline: "Sub-30ms global verification. Passkeys-first. Your data, your control."
  
  primaryCTA: {
    text: "Start Building",
    action: "Sign up flow",
    style: "primary"
  }
  
  secondaryCTA: {
    text: "View Demo",
    action: "Scroll to playground",
    style: "outline"
  }
  
  metrics: [
    { value: "<30ms", label: "Edge Verification" },
    { value: "5 min", label: "Integration Time" },
    { value: "99.99%", label: "Uptime SLA" }
  ]
  
  heroVisual: "Interactive latency map showing global edge performance"
}
```

### 2. Trust Indicators

```typescript
interface TrustSection {
  headline: "Trusted by teams shipping at scale"
  
  logos: [
    "MADFAM",
    "Forge Sight",
    "Aureo Labs",
    // Partner logos
  ]
  
  stats: {
    identitiesManaged: "10M+",
    requestsPerSecond: "50K+",
    globalEdgeLocations: "150+"
  }
}
```

### 3. Core Features Grid

```typescript
interface FeatureSection {
  headline: "Everything you need, nothing you don't"
  
  features: [
    {
      icon: "🚀",
      title: "Edge-Native Performance",
      description: "JWT verification in <30ms globally. 3x faster than Clerk.",
      link: "/docs/edge-verification"
    },
    {
      icon: "🔐",
      title: "Passkeys First",
      description: "WebAuthn native. Not an afterthought, but the primary experience.",
      link: "/docs/passkeys"
    },
    {
      icon: "🌍",
      title: "True Multi-Region",
      description: "Data sovereignty with region pinning. GDPR/CCPA compliant by design.",
      link: "/docs/regions"
    },
    {
      icon: "📊",
      title: "Perfect Audit Trails",
      description: "Event sourced architecture. Time-travel debugging included.",
      link: "/docs/audit"
    },
    {
      icon: "🔌",
      title: "Extensible by Design",
      description: "Plugin architecture. Extend without forking.",
      link: "/docs/plugins"
    },
    {
      icon: "💰",
      title: "Transparent Pricing",
      description: "Simple MAU-based pricing. No hidden fees or gotchas.",
      link: "/pricing"
    }
  ]
}
```

### 4. Developer Experience Showcase

```typescript
interface DeveloperSection {
  headline: "Ship authentication in minutes, not days"
  
  codeExamples: {
    languages: ["TypeScript", "Python", "Go", "Ruby"],
    
    snippets: {
      typescript: `
// 1. Install
npm install @plinto/nextjs @plinto/react-sdk

// 2. Add middleware
export default withPlinto({
  publicRoutes: ['/']
})

// 3. Drop in components
<SignIn />

// Done! Authentication ready in 5 minutes.
      `,
      // Other language examples...
    }
  }
  
  timeline: {
    steps: [
      { time: "0:00", action: "npm install @plinto/sdk" },
      { time: "1:00", action: "Add middleware" },
      { time: "3:00", action: "Configure environment" },
      { time: "4:00", action: "Add UI components" },
      { time: "5:00", action: "Deploy to production" }
    ]
  }
}
```

### 5. Interactive Playground

```typescript
interface PlaygroundSection {
  headline: "Try it live — no signup required"
  
  demo: {
    type: "embedded",
    features: [
      "JWT token generation",
      "Edge verification simulation",
      "Passkey flow demo",
      "Policy evaluation"
    ],
    
    presets: [
      "Basic authentication",
      "Multi-organization RBAC",
      "Enterprise SSO",
      "WebAuthn flow"
    ]
  }
  
  metrics: {
    showRealtime: true,
    displays: ["Latency", "Token size", "Verification time"]
  }
}
```

### 6. Performance Comparison

```typescript
interface ComparisonSection {
  headline: "Built different. Performs better."
  
  comparison: {
    competitors: ["Clerk", "Auth0", "Supabase Auth"],
    
    metrics: [
      {
        metric: "Edge Verification",
        plinto: "<30ms",
        clerk: "50-100ms",
        auth0: "80-150ms",
        supabase: "60-120ms"
      },
      {
        metric: "Global PoPs",
        plinto: "150+",
        clerk: "~30",
        auth0: "~20",
        supabase: "~15"
      },
      {
        metric: "Free Tier MAU",
        plinto: "10,000",
        clerk: "5,000",
        auth0: "7,000",
        supabase: "50,000"
      },
      {
        metric: "Passkey Support",
        plinto: "Native",
        clerk: "Add-on",
        auth0: "Beta",
        supabase: "Planned"
      }
    ]
  }
  
  visualType: "animated-bar-chart"
}
```

### 7. Use Cases

```typescript
interface UseCaseSection {
  headline: "Built for your scale"
  
  cases: [
    {
      title: "B2B SaaS",
      icon: "🏢",
      features: ["Multi-tenant", "SSO/SAML", "Audit logs", "RBAC"],
      cta: "See B2B features"
    },
    {
      title: "Consumer Apps",
      icon: "📱",
      features: ["Social login", "Passkeys", "Magic links", "MFA"],
      cta: "See consumer features"
    },
    {
      title: "Enterprise",
      icon: "🏗️",
      features: ["SCIM", "Region pinning", "SLA", "Support"],
      cta: "Contact sales"
    }
  ]
}
```

### 8. Pricing Preview

```typescript
interface PricingSection {
  headline: "Pricing that scales with you"
  
  tiers: [
    {
      name: "Community",
      price: "$0",
      mau: "10,000 MAU",
      features: ["Core auth", "Passkeys", "Basic audit"],
      cta: "Start free"
    },
    {
      name: "Pro",
      price: "$69",
      mau: "10,000 MAU",
      features: ["Everything in Community", "Webhooks", "RBAC", "Priority support"],
      cta: "Start trial",
      popular: true
    },
    {
      name: "Enterprise",
      price: "Custom",
      features: ["SSO/SCIM", "99.99% SLA", "Dedicated support", "Region pinning"],
      cta: "Contact sales"
    }
  ]
  
  calculator: {
    enabled: true,
    link: "/pricing#calculator"
  }
}
```

### 9. Social Proof

```typescript
interface TestimonialSection {
  headline: "Developers love the experience"
  
  testimonials: [
    {
      quote: "Migrated from Clerk in 2 days. 3x faster verification, half the cost.",
      author: "Sarah Chen",
      role: "CTO, TechStartup",
      avatar: "/testimonials/sarah.jpg"
    },
    {
      quote: "Finally, an auth solution that doesn't lock in our data.",
      author: "Marcus Rodriguez",
      role: "Lead Engineer, ScaleUp",
      avatar: "/testimonials/marcus.jpg"
    }
  ]
  
  caseStudy: {
    company: "Forge Sight",
    metric: "60% faster auth",
    link: "/customers/forge-sight"
  }
}
```

### 10. Call to Action

```typescript
interface CTASection {
  headline: "Ready to own your identity layer?"
  subheadline: "Start with 10,000 free MAU. No credit card required."
  
  primaryCTA: {
    text: "Create Free Account",
    action: "/sign-up",
    style: "large-primary"
  }
  
  alternativeActions: [
    { text: "Schedule Demo", link: "/demo" },
    { text: "Read Docs", link: "/docs" },
    { text: "View Pricing", link: "/pricing" }
  ]
}
```

---

## Interactive Elements

### 1. Latency Globe
- Interactive 3D globe showing edge locations
- Real-time latency measurements
- Click to test from different regions

### 2. Integration Timeline
- Animated timeline showing 5-minute setup
- Interactive code snippets
- Copy-paste ready examples

### 3. Pricing Calculator
- MAU slider with real-time price updates
- Feature comparison at each tier
- ROI calculator vs competitors

### 4. Live Playground
- Embedded code editor
- Real API calls to sandbox environment
- Instant results display

---

## Conversion Optimization

### Primary Conversion Paths

1. **Developer Path**
   - Land → Code examples → Playground → Sign up
   - Optimized for: Quick technical validation

2. **Decision Maker Path**
   - Land → Pricing → Comparison → Case studies → Contact sales
   - Optimized for: Business validation

3. **Migration Path**
   - Land → Compare/Clerk → Migration guide → Start trial
   - Optimized for: Competitive switching

### A/B Testing Strategy

```typescript
interface ABTests {
  heroHeadline: [
    "Identity infrastructure that moves at the speed of your users",
    "The edge-native identity platform",
    "Authentication that doesn't slow you down"
  ],
  
  primaryCTA: [
    "Start Building",
    "Get Started Free",
    "Create Account"
  ],
  
  socialProof: [
    "logoWall",
    "testimonials",
    "metrics"
  ]
}
```

---

## Mobile Experience

### Responsive Design
- Mobile-first approach
- Touch-optimized interactions
- Simplified navigation
- Performance budget: <100KB JS

### Mobile-Specific Features
- Tap to copy code snippets
- Swipeable feature cards
- Compressed hero section
- Bottom sheet navigation

---

## Performance Requirements

### Core Web Vitals
- LCP: <2.5s
- FID: <100ms
- CLS: <0.1
- TTI: <3.5s

### Optimization Strategy
- Static generation for marketing pages
- Edge caching with Cloudflare
- Image optimization with next/image
- Code splitting per route
- Font subsetting

---

## SEO Strategy

### Target Keywords
- Primary: "identity platform", "authentication api"
- Comparison: "clerk alternative", "auth0 vs plinto"
- Technical: "edge authentication", "passkey api"
- Long-tail: "fastest jwt verification", "multi-region auth"

### Technical SEO
- Structured data for features
- OpenGraph optimization
- XML sitemap
- Canonical URLs
- hreflang for regions

---

## Analytics & Tracking

### Key Metrics
- Conversion rate: Sign-ups / Visitors
- Activation rate: First API call / Sign-ups
- Time to value: Sign-up → Production
- Bounce rate by source
- Playground engagement

### Event Tracking
```typescript
interface TrackedEvents {
  signUpStarted: { source: string }
  signUpCompleted: { plan: string }
  playgroundUsed: { feature: string, duration: number }
  codeSnippetCopied: { language: string, section: string }
  pricingCalculatorUsed: { mau: number, estimatedPrice: number }
  comparisonViewed: { competitor: string }
}
```

---

## Implementation Priority

### Phase 1 (Week 1)
- [ ] Hero section with core messaging
- [ ] Feature grid
- [ ] Basic pricing cards
- [ ] Sign-up flow

### Phase 2 (Week 2)
- [ ] Developer experience section
- [ ] Code examples
- [ ] Interactive playground
- [ ] Comparison table

### Phase 3 (Week 3)
- [ ] Latency globe
- [ ] Testimonials
- [ ] Case studies
- [ ] Blog integration

### Phase 4 (Week 4)
- [ ] A/B testing setup
- [ ] Analytics integration
- [ ] Performance optimization
- [ ] SEO implementation

This design creates a marketing entry-point that clearly communicates Plinto's technical superiority while maintaining a smooth path to conversion for both developers and decision-makers.