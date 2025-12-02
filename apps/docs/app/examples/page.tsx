import { ExternalLink, Github, Play, Star } from 'lucide-react'

export default function ExamplesPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 py-12">
      {/* Header */}
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold tracking-tight text-gray-900 dark:text-white sm:text-5xl">
          Examples & Templates
        </h1>
        <p className="mt-6 text-xl leading-8 text-gray-600 dark:text-gray-400 max-w-3xl mx-auto">
          Complete sample applications and code snippets to help you integrate Janua quickly.
          Copy, customize, and deploy in minutes.
        </p>
      </div>

      {/* Featured Examples */}
      <section className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">
          Featured Examples
        </h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <FeaturedExample
            title="Next.js SaaS Starter"
            description="Complete SaaS application with authentication, organizations, billing, and admin dashboard"
            tech={["Next.js 14", "TypeScript", "Tailwind CSS", "Prisma"]}
            githubUrl="https://github.com/madfam-io/nextjs-saas-starter"
            demoUrl="https://nextjs-saas-starter.janua.dev"
            difficulty="Advanced"
            stars={1240}
            featured
          />
          <FeaturedExample
            title="React Dashboard"
            description="Modern admin dashboard with role-based access control and real-time updates"
            tech={["React 18", "TypeScript", "Vite", "TanStack Query"]}
            githubUrl="https://github.com/madfam-io/react-dashboard"
            demoUrl="https://react-dashboard.janua.dev"
            difficulty="Intermediate"
            stars={856}
            featured
          />
        </div>
      </section>

      {/* Framework Examples */}
      <section className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">
          Framework Examples
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <ExampleCard
            title="Next.js App Router"
            description="Modern Next.js app with App Router, server components, and middleware"
            tech={["Next.js 14", "TypeScript", "App Router"]}
            githubUrl="https://github.com/madfam-io/nextjs-app-router-example"
            demoUrl="https://nextjs-app-router.janua.dev"
            difficulty="Beginner"
          />
          <ExampleCard
            title="Next.js Pages Router"
            description="Traditional Next.js setup with Pages Router and API routes"
            tech={["Next.js 13", "TypeScript", "Pages Router"]}
            githubUrl="https://github.com/madfam-io/nextjs-pages-router-example"
            demoUrl="https://nextjs-pages-router.janua.dev"
            difficulty="Beginner"
          />
          <ExampleCard
            title="React + Vite SPA"
            description="Single-page application with React Router and modern tooling"
            tech={["React 18", "Vite", "React Router"]}
            githubUrl="https://github.com/madfam-io/react-vite-spa-example"
            demoUrl="https://react-vite-spa.janua.dev"
            difficulty="Beginner"
          />
          <ExampleCard
            title="Vue 3 + Nuxt"
            description="Full-stack Vue application with Nuxt 3 and server-side rendering"
            tech={["Vue 3", "Nuxt 3", "TypeScript"]}
            githubUrl="https://github.com/madfam-io/vue-nuxt-example"
            demoUrl="https://vue-nuxt.janua.dev"
            difficulty="Intermediate"
          />
          <ExampleCard
            title="Express API"
            description="Node.js REST API with Express and authentication middleware"
            tech={["Express", "Node.js", "TypeScript"]}
            githubUrl="https://github.com/madfam-io/express-api-example"
            demoUrl="https://express-api.janua.dev"
            difficulty="Intermediate"
          />
          <ExampleCard
            title="FastAPI Backend"
            description="Python API with FastAPI, async/await, and OpenAPI documentation"
            tech={["FastAPI", "Python", "Pydantic"]}
            githubUrl="https://github.com/madfam-io/fastapi-example"
            demoUrl="https://fastapi.janua.dev"
            difficulty="Intermediate"
          />
        </div>
      </section>

      {/* Use Case Examples */}
      <section className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">
          Use Case Examples
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <UseCaseExample
            title="E-commerce Store"
            description="Complete online store with user accounts, order management, and payment integration"
            features={["User Registration", "Shopping Cart", "Order History", "Admin Panel"]}
            tech={["Next.js", "Stripe", "Prisma", "PostgreSQL"]}
            githubUrl="https://github.com/madfam-io/ecommerce-example"
            demoUrl="https://ecommerce.janua.dev"
          />
          <UseCaseExample
            title="SaaS Application"
            description="Multi-tenant SaaS with organizations, billing, and feature flags"
            features={["Organizations", "RBAC", "Billing", "Feature Flags"]}
            tech={["Next.js", "Stripe", "Vercel", "PlanetScale"]}
            githubUrl="https://github.com/madfam-io/saas-example"
            demoUrl="https://saas.janua.dev"
          />
          <UseCaseExample
            title="Social Platform"
            description="Social networking app with user profiles, posts, and real-time chat"
            features={["User Profiles", "Posts & Comments", "Real-time Chat", "File Uploads"]}
            tech={["React", "Socket.io", "MongoDB", "Cloudinary"]}
            githubUrl="https://github.com/madfam-io/social-platform-example"
            demoUrl="https://social.janua.dev"
          />
          <UseCaseExample
            title="Project Management"
            description="Team collaboration tool with projects, tasks, and time tracking"
            features={["Team Management", "Projects & Tasks", "Time Tracking", "Notifications"]}
            tech={["Vue", "Nuxt", "Supabase", "Tailwind"]}
            githubUrl="https://github.com/madfam-io/project-management-example"
            demoUrl="https://pm.janua.dev"
          />
        </div>
      </section>

      {/* Code Snippets */}
      <section className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">
          Code Snippets
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <CodeSnippet
            title="Protect API Route"
            description="Secure your API endpoints with middleware"
            _language="TypeScript"
            code={`export async function GET(request: NextRequest) {
  const session = await janua.getSession(request)
  
  if (!session) {
    return new Response('Unauthorized', { status: 401 })
  }
  
  return Response.json({ user: session.user })
}`}
          />
          <CodeSnippet
            title="Login Component"
            description="React component for user authentication"
            _language="TypeScript"
            code={`export function LoginForm() {
  const { signIn, loading } = useJanua()
  
  const handleSubmit = async (e) => {
    e.preventDefault()
    await signIn({ email, password })
  }
  
  return <form onSubmit={handleSubmit}>...</form>
}`}
          />
          <CodeSnippet
            title="Protected Route"
            description="Client-side route protection"
            _language="TypeScript"
            code={`export function ProtectedRoute({ children }) {
  const { user, loading } = useJanua()
  
  if (loading) return <Loading />
  if (!user) return <Navigate to="/login" />
  
  return children
}`}
          />
          <CodeSnippet
            title="User Profile"
            description="Display and update user information"
            _language="TypeScript"
            code={`export function UserProfile() {
  const { user, updateProfile } = useJanua()
  
  const handleUpdate = async (data) => {
    await updateProfile(data)
  }
  
  return <ProfileForm user={user} onUpdate={handleUpdate} />
}`}
          />
        </div>
      </section>

      {/* Starter Templates */}
      <section className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">
          Starter Templates
        </h2>
        <div className="space-y-4">
          <StarterTemplate
            name="create-janua-app"
            description="CLI tool to scaffold new applications with Janua authentication"
            command="npx create-janua-app my-app"
            frameworks={["Next.js", "React", "Vue", "Express"]}
          />
          <StarterTemplate
            name="Vercel Template"
            description="One-click deployment template for Vercel"
            command="Deploy with Vercel"
            frameworks={["Next.js"]}
            deployUrl="https://vercel.com/new/clone?repository-url=https://github.com/madfam-io/nextjs-starter"
          />
          <StarterTemplate
            name="Netlify Template"
            description="One-click deployment template for Netlify"
            command="Deploy to Netlify"
            frameworks={["React", "Vue"]}
            deployUrl="https://app.netlify.com/start/deploy?repository=https://github.com/madfam-io/react-starter"
          />
        </div>
      </section>

      {/* Community Examples */}
      <section>
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">
          Community Examples
        </h2>
        <div className="bg-blue-50 dark:bg-blue-950 rounded-lg p-6 mb-6">
          <p className="text-blue-800 dark:text-blue-200 mb-4">
            Community examples are built and maintained by the Janua community.
            Want to add your example? <a href="mailto:examples@janua.dev" className="underline">Contact us</a> or submit a PR!
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <CommunityExample
            title="Svelte SPA"
            description="SvelteKit application with authentication"
            author="@johndoe"
            tech={["Svelte", "SvelteKit", "TypeScript"]}
            githubUrl="https://github.com/community/svelte-janua-example"
          />
          <CommunityExample
            title="Angular Dashboard"
            description="Angular admin dashboard with guards and services"
            author="@janedoe"
            tech={["Angular", "TypeScript", "RxJS"]}
            githubUrl="https://github.com/community/angular-janua-example"
          />
        </div>
      </section>
    </div>
  )
}

function FeaturedExample({ title, description, tech, githubUrl, demoUrl, difficulty, stars, featured }: {
  title: string
  description: string
  tech: string[]
  githubUrl: string
  demoUrl: string
  difficulty: string
  stars: number
  featured?: boolean
}) {
  return (
    <div className={`border rounded-lg p-6 ${featured ? 'border-blue-600 dark:border-blue-400 bg-blue-50 dark:bg-blue-950' : 'border-gray-200 dark:border-gray-800'}`}>
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-xl font-semibold text-gray-900 dark:text-white">
            {title}
          </h3>
          <p className="text-gray-600 dark:text-gray-400 mt-2">
            {description}
          </p>
        </div>
        {featured && (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
            Featured
          </span>
        )}
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        {tech.map((item, index) => (
          <span
            key={index}
            className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200"
          >
            {item}
          </span>
        ))}
      </div>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <a href={githubUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center text-sm font-medium text-gray-600 dark:text-gray-400 hover:underline">
            <Github className="w-4 h-4 mr-1" />
            Code
          </a>
          <a href={demoUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline">
            <ExternalLink className="w-4 h-4 mr-1" />
            Demo
          </a>
          <div className="flex items-center text-sm text-gray-500 dark:text-gray-500">
            <Star className="w-4 h-4 mr-1" />
            {stars}
          </div>
        </div>
        <span className={`px-2 py-1 rounded-md text-xs font-medium ${
          difficulty === 'Beginner' ? 'bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300' :
          difficulty === 'Intermediate' ? 'bg-yellow-100 dark:bg-yellow-900 text-yellow-700 dark:text-yellow-300' :
          'bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-300'
        }`}>
          {difficulty}
        </span>
      </div>
    </div>
  )
}

function ExampleCard({ title, description, tech, githubUrl, demoUrl, difficulty }: {
  title: string
  description: string
  tech: string[]
  githubUrl: string
  demoUrl: string
  difficulty: string
}) {
  return (
    <div className="border border-gray-200 dark:border-gray-800 rounded-lg p-6">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
        {title}
      </h3>
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
        {description}
      </p>

      <div className="flex flex-wrap gap-1 mb-4">
        {tech.map((item, index) => (
          <span
            key={index}
            className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200"
          >
            {item}
          </span>
        ))}
      </div>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <a href={githubUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center text-sm font-medium text-gray-600 dark:text-gray-400 hover:underline">
            <Github className="w-4 h-4 mr-1" />
            Code
          </a>
          <a href={demoUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline">
            <Play className="w-4 h-4 mr-1" />
            Demo
          </a>
        </div>
        <span className={`px-2 py-1 rounded-md text-xs font-medium ${
          difficulty === 'Beginner' ? 'bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300' :
          difficulty === 'Intermediate' ? 'bg-yellow-100 dark:bg-yellow-900 text-yellow-700 dark:text-yellow-300' :
          'bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-300'
        }`}>
          {difficulty}
        </span>
      </div>
    </div>
  )
}

function UseCaseExample({ title, description, features, tech, githubUrl, demoUrl }: {
  title: string
  description: string
  features: string[]
  tech: string[]
  githubUrl: string
  demoUrl: string
}) {
  return (
    <div className="border border-gray-200 dark:border-gray-800 rounded-lg p-6">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
        {title}
      </h3>
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
        {description}
      </p>

      <div className="mb-4">
        <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-2">Features:</h4>
        <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
          {features.map((feature, index) => (
            <li key={index} className="flex items-center">
              <span className="w-1.5 h-1.5 bg-blue-600 rounded-full mr-2"></span>
              {feature}
            </li>
          ))}
        </ul>
      </div>

      <div className="flex flex-wrap gap-1 mb-4">
        {tech.map((item, index) => (
          <span
            key={index}
            className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200"
          >
            {item}
          </span>
        ))}
      </div>

      <div className="flex items-center gap-3">
        <a href={githubUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center text-sm font-medium text-gray-600 dark:text-gray-400 hover:underline">
          <Github className="w-4 h-4 mr-1" />
          Code
        </a>
        <a href={demoUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline">
          <ExternalLink className="w-4 h-4 mr-1" />
          Demo
        </a>
      </div>
    </div>
  )
}

function CodeSnippet({ title, description, _language, code }: {
  title: string
  description: string
  _language: string
  code: string
}) {
  return (
    <div className="border border-gray-200 dark:border-gray-800 rounded-lg">
      <div className="p-4 border-b border-gray-200 dark:border-gray-800">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
          {title}
        </h3>
        <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
          {description}
        </p>
      </div>
      <div className="p-4">
        <pre className="text-xs bg-gray-900 text-gray-300 p-3 rounded overflow-x-auto">
          <code>{code}</code>
        </pre>
      </div>
    </div>
  )
}

function StarterTemplate({ name, description, command, frameworks, deployUrl }: {
  name: string
  description: string
  command: string
  frameworks: string[]
  deployUrl?: string
}) {
  return (
    <div className="border border-gray-200 dark:border-gray-800 rounded-lg p-6">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            {name}
          </h3>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            {description}
          </p>
          <div className="flex flex-wrap gap-2 mt-3">
            {frameworks.map((framework, index) => (
              <span
                key={index}
                className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
              >
                {framework}
              </span>
            ))}
          </div>
        </div>
        <div className="flex flex-col gap-2">
          <code className="text-sm bg-gray-100 dark:bg-gray-900 px-3 py-2 rounded">
            {command}
          </code>
          {deployUrl && (
            <a href={deployUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline">
              <ExternalLink className="w-4 h-4 mr-1" />
              Deploy Now
            </a>
          )}
        </div>
      </div>
    </div>
  )
}

function CommunityExample({ title, description, author, tech, githubUrl }: {
  title: string
  description: string
  author: string
  tech: string[]
  githubUrl: string
}) {
  return (
    <div className="border border-gray-200 dark:border-gray-800 rounded-lg p-6">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            {title}
          </h3>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            {description}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-500 mt-1">
            by {author}
          </p>
        </div>
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">
          Community
        </span>
      </div>

      <div className="flex flex-wrap gap-1 mb-4">
        {tech.map((item, index) => (
          <span
            key={index}
            className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200"
          >
            {item}
          </span>
        ))}
      </div>

      <a href={githubUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center text-sm font-medium text-gray-600 dark:text-gray-400 hover:underline">
        <Github className="w-4 h-4 mr-1" />
        View Code
      </a>
    </div>
  )
}