export interface SearchResult {
  id: string
  title: string
  description: string
  url: string
  type: 'guide' | 'api' | 'example' | 'reference' | 'sdk'
  section?: string
  content?: string
}

// Real search data indexed from our documentation
export const searchData: SearchResult[] = [
  // Getting Started
  {
    id: 'getting-started',
    title: 'Getting Started',
    description: 'Complete guide to integrating Plinto into your application',
    url: '/getting-started',
    type: 'guide',
    section: 'Getting Started',
    content: 'getting started plinto integration authentication setup install configure'
  },
  {
    id: 'quick-start',
    title: 'Quick Start Guide',
    description: 'Get up and running with Plinto in under 5 minutes',
    url: '/getting-started/quick-start',
    type: 'guide',
    section: 'Getting Started',
    content: 'quick start 5 minutes install npm sdk environment variables authentication login'
  },
  {
    id: 'installation',
    title: 'Installation Guide',
    description: 'Detailed installation instructions for all frameworks',
    url: '/getting-started/installation',
    type: 'guide',
    section: 'Getting Started',
    content: 'installation setup environment variables nodejs python go frameworks'
  },

  // Authentication Guide
  {
    id: 'authentication',
    title: 'Authentication Guide',
    description: 'Learn about different authentication methods and implementation patterns',
    url: '/guides/authentication',
    type: 'guide',
    section: 'Guides',
    content: 'authentication email password passkeys webauthn social login oauth mfa multi factor'
  },
  {
    id: 'passkeys',
    title: 'Implementing Passkeys',
    description: 'Step-by-step guide to passwordless authentication with WebAuthn',
    url: '/guides/authentication/passkeys',
    type: 'guide',
    section: 'Authentication',
    content: 'passkeys webauthn passwordless biometric fingerprint face id security'
  },
  {
    id: 'social-login',
    title: 'Social Login',
    description: 'Integrate OAuth providers like Google, GitHub, and Microsoft',
    url: '/guides/authentication/social',
    type: 'guide',
    section: 'Authentication',
    content: 'social login oauth google github microsoft apple discord twitter linkedin'
  },

  // API Reference
  {
    id: 'api-reference',
    title: 'API Reference',
    description: 'Complete API documentation with examples',
    url: '/api',
    type: 'api',
    section: 'API Reference',
    content: 'api reference endpoints authentication signin signup tokens jwt refresh'
  },
  {
    id: 'auth-signin',
    title: 'POST /api/v1/auth/signin',
    description: 'Sign in with email and password',
    url: '/api#signin',
    type: 'api',
    section: 'Authentication API',
    content: 'signin sign in login email password authentication jwt tokens'
  },
  {
    id: 'auth-signup',
    title: 'POST /api/v1/auth/signup',
    description: 'Create a new user account',
    url: '/api#signup',
    type: 'api',
    section: 'Authentication API',
    content: 'signup sign up register create account email password user'
  },
  {
    id: 'auth-refresh',
    title: 'POST /api/v1/auth/refresh',
    description: 'Refresh access token using refresh token',
    url: '/api#refresh',
    type: 'api',
    section: 'Authentication API',
    content: 'refresh token access token jwt renew authentication'
  },
  {
    id: 'auth-me',
    title: 'GET /api/v1/auth/me',
    description: 'Get current user information',
    url: '/api#me',
    type: 'api',
    section: 'Authentication API',
    content: 'user profile information current user authenticated session'
  },

  // SDKs
  {
    id: 'sdks',
    title: 'SDKs & Libraries',
    description: 'Official SDKs for JavaScript, Python, Go, and more',
    url: '/sdks',
    type: 'sdk',
    section: 'SDKs',
    content: 'sdk library javascript typescript react nextjs vue python django fastapi go'
  },
  {
    id: 'nextjs-sdk',
    title: '@plinto/nextjs',
    description: 'Next.js SDK with App Router and Pages Router support',
    url: '/sdks/javascript/nextjs',
    type: 'sdk',
    section: 'JavaScript SDKs',
    content: 'nextjs next.js app router pages router middleware server components api routes'
  },
  {
    id: 'react-sdk',
    title: '@plinto/react-sdk',
    description: 'React hooks and components for authentication',
    url: '/sdks/javascript/react',
    type: 'sdk',
    section: 'JavaScript SDKs',
    content: 'react hooks components context provider spa single page application'
  },
  {
    id: 'vue-sdk',
    title: '@plinto/vue',
    description: 'Vue 3 composables and plugin',
    url: '/sdks/javascript/vue',
    type: 'sdk',
    section: 'JavaScript SDKs',
    content: 'vue vue3 nuxt composables plugin pinia typescript'
  },
  {
    id: 'python-sdk',
    title: 'plinto-python',
    description: 'Python SDK with async/await support',
    url: '/sdks/python',
    type: 'sdk',
    section: 'Python SDKs',
    content: 'python async await fastapi django flask backend api server'
  },

  // Examples
  {
    id: 'examples',
    title: 'Examples & Templates',
    description: 'Complete sample applications and code snippets',
    url: '/examples',
    type: 'example',
    section: 'Examples',
    content: 'examples templates sample applications starter code snippets'
  },
  {
    id: 'nextjs-saas-starter',
    title: 'Next.js SaaS Starter',
    description: 'Complete SaaS application with authentication and billing',
    url: '/examples/nextjs-saas',
    type: 'example',
    section: 'Featured Examples',
    content: 'nextjs saas starter billing organizations multi tenant dashboard'
  },
  {
    id: 'react-dashboard',
    title: 'React Dashboard',
    description: 'Admin dashboard with role-based access control',
    url: '/examples/react-dashboard',
    type: 'example',
    section: 'Featured Examples',
    content: 'react dashboard admin rbac role based access control real time'
  },
  {
    id: 'ecommerce-example',
    title: 'E-commerce Store',
    description: 'Online store with user accounts and order management',
    url: '/examples/ecommerce',
    type: 'example',
    section: 'Use Case Examples',
    content: 'ecommerce store shopping cart orders payment stripe checkout'
  },

  // Guides
  {
    id: 'guides',
    title: 'Guides',
    description: 'Comprehensive guides covering every aspect of Plinto',
    url: '/guides',
    type: 'guide',
    section: 'Guides',
    content: 'guides tutorials documentation help learn how to'
  },
  {
    id: 'session-management',
    title: 'Session Management',
    description: 'Handle user sessions, refresh tokens, and device management',
    url: '/guides/sessions',
    type: 'guide',
    section: 'Guides',
    content: 'session management jwt tokens refresh device tracking security logout'
  },
  {
    id: 'user-management',
    title: 'User Management',
    description: 'Complete user lifecycle management',
    url: '/guides/users',
    type: 'guide',
    section: 'Guides',
    content: 'user management profile registration verification password reset metadata'
  },
  {
    id: 'security-guide',
    title: 'Security Best Practices',
    description: 'Secure your application and protect user data',
    url: '/guides/security',
    type: 'guide',
    section: 'Guides',
    content: 'security best practices rate limiting csrf protection audit logging'
  },
  {
    id: 'organizations',
    title: 'Organizations',
    description: 'Multi-tenant architecture with role-based access control',
    url: '/guides/organizations',
    type: 'guide',
    section: 'Guides',
    content: 'organizations multi tenant rbac team management saas'
  },

  // Framework-specific guides
  {
    id: 'nextjs-integration',
    title: 'Next.js Integration',
    description: 'Complete integration guide for Next.js applications',
    url: '/guides/frameworks/nextjs',
    type: 'guide',
    section: 'Framework Guides',
    content: 'nextjs integration app router pages router middleware server components'
  },
  {
    id: 'react-integration',
    title: 'React Integration',
    description: 'Integrate Plinto with React applications',
    url: '/guides/frameworks/react',
    type: 'guide',
    section: 'Framework Guides',
    content: 'react integration hooks components spa vite create react app'
  },
  {
    id: 'vue-integration',
    title: 'Vue Integration',
    description: 'Vue.js and Nuxt integration guide',
    url: '/guides/frameworks/vue',
    type: 'guide',
    section: 'Framework Guides',
    content: 'vue vuejs nuxt integration composables plugin store'
  }
]

export function searchDocumentation(query: string): SearchResult[] {
  if (!query || query.length < 2) {
    return []
  }

  const searchTerms = query.toLowerCase().split(' ').filter(term => term.length > 1)
  
  return searchData
    .map(item => {
      let score = 0
      const titleLower = item.title.toLowerCase()
      const descriptionLower = item.description.toLowerCase()
      const contentLower = item.content?.toLowerCase() || ''
      const sectionLower = item.section?.toLowerCase() || ''

      // Exact title match (highest priority)
      if (titleLower === query.toLowerCase()) {
        score += 100
      }

      // Title contains query
      if (titleLower.includes(query.toLowerCase())) {
        score += 50
      }

      // Description contains query
      if (descriptionLower.includes(query.toLowerCase())) {
        score += 30
      }

      // Section match
      if (sectionLower.includes(query.toLowerCase())) {
        score += 20
      }

      // Individual term matches
      searchTerms.forEach(term => {
        if (titleLower.includes(term)) score += 10
        if (descriptionLower.includes(term)) score += 5
        if (contentLower.includes(term)) score += 3
        if (sectionLower.includes(term)) score += 2
      })

      // Type-based scoring
      if (item.type === 'guide' && (query.includes('guide') || query.includes('how'))) {
        score += 15
      }
      if (item.type === 'api' && (query.includes('api') || query.includes('endpoint'))) {
        score += 15
      }
      if (item.type === 'example' && (query.includes('example') || query.includes('template'))) {
        score += 15
      }
      if (item.type === 'sdk' && (query.includes('sdk') || query.includes('library'))) {
        score += 15
      }

      return { ...item, score }
    })
    .filter(item => item.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 8) // Limit to top 8 results
}