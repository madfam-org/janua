'use client'

import { motion } from 'framer-motion'
import { useInView } from 'react-intersection-observer'
import { Terminal } from 'lucide-react'

// Three real steps. The commands and code below come from:
// - docker-compose.yml at repo root
// - packages/nextjs-sdk usage docs
// - apps/api/app/routers/v1/users.py (POST /api/v1/auth/signup)
const steps = [
  {
    n: '01',
    title: 'Run it',
    body: 'Pull the repo, copy the example env, bring it up. Postgres + API + dashboard come up together.',
    code: `git clone https://github.com/madfam-io/janua
cd janua
cp .env.example .env
docker compose up`,
  },
  {
    n: '02',
    title: 'Wire your app',
    body: 'Install the SDK that matches your stack. The Next.js middleware below is six lines. Other SDKs follow the same shape.',
    code: `// middleware.ts
import { withJanua } from '@janua/nextjs/middleware'

export default withJanua({
  publicRoutes: ['/', '/login'],
})`,
  },
  {
    n: '03',
    title: 'Get an authed user',
    body: 'Email + password works out of the box. Passkeys, MFA, and OAuth providers are toggles, not redeploys.',
    code: `curl -X POST http://localhost:8000/api/v1/auth/signup \\
  -H "Content-Type: application/json" \\
  -d '{
    "email": "you@yourapp.com",
    "password": "first-real-password",
    "first_name": "Ada"
  }'`,
  },
]

export function HowItWorks() {
  const [ref, inView] = useInView({ triggerOnce: true, threshold: 0.1 })

  return (
    <section
      ref={ref}
      className="py-24 px-4 sm:px-6 lg:px-8 bg-white dark:bg-slate-950"
    >
      <div className="max-w-7xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6 }}
          className="text-center mb-16 max-w-3xl mx-auto"
        >
          <h2 className="text-4xl sm:text-5xl font-bold text-slate-900 dark:text-white mb-6">
            Three steps. Real commands.
          </h2>
          <p className="text-xl text-slate-600 dark:text-slate-300">
            From clone to first authenticated user. Copy-paste, don't take our
            word for it.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {steps.map((step, i) => (
            <motion.div
              key={step.n}
              initial={{ opacity: 0, y: 20 }}
              animate={inView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.5, delay: i * 0.1 }}
              className="bg-slate-50 dark:bg-slate-900 rounded-2xl p-6 border border-slate-200 dark:border-slate-800"
            >
              <div className="flex items-center gap-3 mb-3">
                <span className="text-sm font-mono text-blue-600 dark:text-blue-400">
                  {step.n}
                </span>
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                  {step.title}
                </h3>
              </div>
              <p className="text-sm text-slate-600 dark:text-slate-400 mb-4">
                {step.body}
              </p>
              <div className="rounded-lg bg-slate-950 p-4 overflow-x-auto">
                <div className="flex items-center gap-2 mb-2 text-xs text-slate-500">
                  <Terminal className="w-3 h-3" />
                  <span>step {step.n}</span>
                </div>
                <pre className="text-xs text-slate-100 leading-relaxed whitespace-pre">
                  <code>{step.code}</code>
                </pre>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
