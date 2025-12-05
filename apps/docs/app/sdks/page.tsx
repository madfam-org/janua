import Link from 'next/link'
import { BookOpen, Github, ExternalLink } from 'lucide-react'

export default function SDKsPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 py-12">
      {/* Header */}
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold tracking-tight text-gray-900 dark:text-white sm:text-5xl">
          Janua SDKs
        </h1>
        <p className="mt-6 text-xl leading-8 text-gray-600 dark:text-gray-400 max-w-3xl mx-auto">
          Official SDKs and libraries for integrating Janua into your applications.
          Choose your preferred language and framework.
        </p>
      </div>

      {/* JavaScript/TypeScript SDKs */}
      <section className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">
          JavaScript / TypeScript
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <SDKCard
            name="@janua/nextjs"
            description="Complete Next.js integration with App Router and Pages Router support"
            version="1.2.0"
            href="/sdks/javascript/nextjs"
            githubUrl="https://github.com/madfam-io/janua-nextjs"
            installCommand="npm install @janua/nextjs"
            features={["App Router Support", "Middleware Integration", "Server Components", "API Routes"]}
            stable
          />
          <SDKCard
            name="@janua/react-sdk"
            description="React hooks and components for authentication"
            version="1.1.8"
            href="/sdks/javascript/react"
            githubUrl="https://github.com/madfam-io/janua-react"
            installCommand="npm install @janua/react-sdk"
            features={["React Hooks", "Context Provider", "Auth Components", "TypeScript Support"]}
            stable
          />
          <SDKCard
            name="@janua/vue"
            description="Vue 3 composables and plugin for authentication"
            version="1.0.5"
            href="/sdks/javascript/vue"
            githubUrl="https://github.com/madfam-io/janua-vue"
            installCommand="npm install @janua/vue"
            features={["Vue 3 Composables", "Pinia Integration", "TypeScript Support", "Nuxt 3 Compatible"]}
            stable
          />
          <SDKCard
            name="@janua/typescript-sdk"
            description="Universal TypeScript SDK for any framework"
            version="1.2.1"
            href="/sdks/javascript/universal"
            githubUrl="https://github.com/madfam-io/janua-typescript"
            installCommand="npm install @janua/typescript-sdk"
            features={["Framework Agnostic", "Node.js Support", "Browser Support", "Full TypeScript Support"]}
            stable
          />
        </div>
      </section>

      {/* Python SDKs */}
      <section className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">
          Python
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <SDKCard
            name="janua-python"
            description="Official Python SDK with async/await support"
            version="0.8.2"
            href="/sdks/python"
            githubUrl="https://github.com/madfam-io/janua-python"
            installCommand="pip install janua-python"
            features={["Async/Await Support", "Type Hints", "Pydantic Models", "Framework Agnostic"]}
            stable
          />
          <SDKCard
            name="janua-django"
            description="Django integration with middleware and decorators"
            version="0.6.0"
            href="/sdks/python/django"
            githubUrl="https://github.com/madfam-io/janua-django"
            installCommand="pip install janua-django"
            features={["Middleware", "Decorators", "Admin Integration", "User Model"]}
            stable
          />
          <SDKCard
            name="janua-fastapi"
            description="FastAPI plugin with dependency injection"
            version="0.5.1"
            href="/sdks/python/fastapi"
            githubUrl="https://github.com/madfam-io/janua-fastapi"
            installCommand="pip install janua-fastapi"
            features={["Dependency Injection", "OAuth2 Scopes", "OpenAPI Integration", "Async Support"]}
            stable
          />
          <SDKCard
            name="janua-flask"
            description="Flask extension for authentication"
            version="0.4.2"
            href="/sdks/python/flask"
            githubUrl="https://github.com/madfam-io/janua-flask"
            installCommand="pip install janua-flask"
            features={["Flask Extension", "Session Management", "Decorators", "Blueprint Support"]}
            beta
          />
        </div>
      </section>

      {/* Other Languages */}
      <section className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">
          Other Languages
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <SDKCard
            name="janua-go"
            description="Go SDK with Gin and standard library support"
            version="0.3.0"
            href="/sdks/go"
            githubUrl="https://github.com/madfam-io/janua-go"
            installCommand="go get github.com/madfam-io/janua-go"
            features={["Standard Library", "Gin Integration", "JWT Validation", "Middleware Support"]}
            beta
          />
          <SDKCard
            name="janua-php"
            description="PHP SDK with Laravel and Symfony support"
            version="0.2.1"
            href="/sdks/php"
            githubUrl="https://github.com/madfam-io/janua-php"
            installCommand="composer require janua/janua-php"
            features={["Laravel Support", "Symfony Bundle", "PSR-7 Compatible", "JWT Validation"]}
            alpha
          />
          <SDKCard
            name="janua-rust"
            description="Rust crate for server-side authentication"
            version="0.1.5"
            href="/sdks/rust"
            githubUrl="https://github.com/madfam-io/janua-rust"
            installCommand="cargo add janua"
            features={["Axum Integration", "Async/Await", "Type Safety", "JWT Validation"]}
            alpha
          />
          <SDKCard
            name="janua-ruby"
            description="Ruby gem with Rails integration"
            version="0.1.2"
            href="/sdks/ruby"
            githubUrl="https://github.com/madfam-io/janua-ruby"
            installCommand="gem install janua"
            features={["Rails Integration", "Rack Middleware", "ActiveRecord", "JWT Validation"]}
            alpha
          />
        </div>
      </section>

      {/* Mobile SDKs */}
      <section className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">
          Mobile
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <SDKCard
            name="@janua/react-sdk-native"
            description="React Native SDK with biometric authentication"
            version="0.7.0"
            href="/sdks/mobile/react-native"
            githubUrl="https://github.com/madfam-io/janua-react-native"
            installCommand="npm install @janua/react-sdk-native"
            features={["Biometric Auth", "Keychain Storage", "Deep Linking", "Push Notifications"]}
            beta
          />
          <SDKCard
            name="janua_flutter"
            description="Flutter plugin for cross-platform mobile apps"
            version="0.6.2"
            href="/sdks/mobile/flutter"
            githubUrl="https://github.com/madfam-io/janua-flutter"
            installCommand="flutter pub add janua_flutter"
            features={["Cross Platform", "Secure Storage", "Biometric Auth", "Deep Linking"]}
            beta
          />
        </div>
      </section>

      {/* Community SDKs */}
      <section className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">
          Community SDKs
        </h2>
        <div className="bg-yellow-50 dark:bg-yellow-950 rounded-lg p-6 mb-6">
          <p className="text-yellow-800 dark:text-yellow-200">
            Community SDKs are maintained by the community and may not be officially supported.
            Use at your own discretion and contribute back when possible.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <CommunitySDKCard
            name="janua-svelte"
            description="SvelteKit integration with stores and actions"
            maintainer="@johndoe"
            githubUrl="https://github.com/madfam-io/janua"
            installCommand="npm install janua-svelte"
          />
          <CommunitySDKCard
            name="janua-angular"
            description="Angular services and guards for authentication"
            maintainer="@janedoe"
            githubUrl="https://github.com/madfam-io/janua"
            installCommand="npm install janua-angular"
          />
        </div>
      </section>

      {/* SDK Comparison */}
      <section className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">
          Choose the Right SDK
        </h2>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-800">
            <thead className="bg-gray-50 dark:bg-gray-900">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Framework
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  SDK
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Use Case
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Status
                </th>
              </tr>
            </thead>
            <tbody className="bg-white dark:bg-gray-950 divide-y divide-gray-200 dark:divide-gray-800">
              <tr>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">
                  Next.js
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                  @janua/nextjs
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                  Full-stack React applications
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                    Stable
                  </span>
                </td>
              </tr>
              <tr>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">
                  React SPA
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                  @janua/react-sdk
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                  Single-page applications
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                    Stable
                  </span>
                </td>
              </tr>
              <tr>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">
                  Vue / Nuxt
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                  @janua/vue
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                  Vue.js applications
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                    Stable
                  </span>
                </td>
              </tr>
              <tr>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">
                  Python API
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                  janua-python
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                  Backend services and APIs
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                    Stable
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* Getting Started */}
      <section>
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">
            Ready to Get Started?
          </h2>
          <div className="space-y-4 sm:space-y-0 sm:space-x-4 sm:flex sm:justify-center">
            <Link href="/getting-started/quick-start">
              <button className="inline-flex items-center px-6 py-3 border border-transparent text-base font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700">
                Quick Start Guide
              </button>
            </Link>
            <Link href="/examples">
              <button className="inline-flex items-center px-6 py-3 border border-gray-300 dark:border-gray-700 text-base font-medium rounded-md text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-900 hover:bg-gray-50 dark:hover:bg-gray-800">
                View Examples
              </button>
            </Link>
          </div>
        </div>
      </section>
    </div>
  )
}

function SDKCard({ name, description, version, href, githubUrl, installCommand, features, stable = false, beta = false, alpha = false }: {
  name: string
  description: string
  version: string
  href: string
  githubUrl: string
  installCommand: string
  features: string[]
  stable?: boolean
  beta?: boolean
  alpha?: boolean
}) {
  const status = stable ? 'Stable' : beta ? 'Beta' : alpha ? 'Alpha' : 'Development'
  const statusColor = stable ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' :
                     beta ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200' :
                     'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'

  return (
    <div className="border border-gray-200 dark:border-gray-800 rounded-lg p-6">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            {name}
          </h3>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            {description}
          </p>
        </div>
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusColor}`}>
          {status}
        </span>
      </div>

      <div className="mb-4">
        <code className="text-sm bg-gray-100 dark:bg-gray-900 px-2 py-1 rounded">
          {installCommand}
        </code>
        <span className="text-sm text-gray-500 dark:text-gray-500 ml-2">
          v{version}
        </span>
      </div>

      <div className="mb-4">
        <div className="flex flex-wrap gap-1">
          {features.map((feature, index) => (
            <span
              key={index}
              className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200"
            >
              {feature}
            </span>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Link href={href} className="inline-flex items-center text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline">
          <BookOpen className="w-4 h-4 mr-1" />
          Documentation
        </Link>
        <a href={githubUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center text-sm font-medium text-gray-600 dark:text-gray-400 hover:underline">
          <Github className="w-4 h-4 mr-1" />
          GitHub
        </a>
      </div>
    </div>
  )
}

function CommunitySDKCard({ name, description, maintainer, githubUrl, installCommand }: {
  name: string
  description: string
  maintainer: string
  githubUrl: string
  installCommand: string
}) {
  return (
    <div className="border border-gray-200 dark:border-gray-800 rounded-lg p-6">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            {name}
          </h3>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            {description}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">
            Maintained by {maintainer}
          </p>
        </div>
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200">
          Community
        </span>
      </div>

      <div className="mb-4">
        <code className="text-sm bg-gray-100 dark:bg-gray-900 px-2 py-1 rounded">
          {installCommand}
        </code>
      </div>

      <div className="flex items-center gap-3">
        <a href={githubUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center text-sm font-medium text-gray-600 dark:text-gray-400 hover:underline">
          <Github className="w-4 h-4 mr-1" />
          GitHub
        </a>
        <a href={githubUrl + '/issues'} target="_blank" rel="noopener noreferrer" className="inline-flex items-center text-sm font-medium text-gray-600 dark:text-gray-400 hover:underline">
          <ExternalLink className="w-4 h-4 mr-1" />
          Report Issues
        </a>
      </div>
    </div>
  )
}