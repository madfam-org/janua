'use client'

import { motion } from 'framer-motion'
import { useInView } from 'react-intersection-observer'
import { Star, Quote, ArrowRight } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

const testimonials = [
  {
    content: "Plinto cut our authentication implementation from weeks to hours. The passkeys integration is seamless, and our users love the passwordless experience. Best decision we made for our platform.",
    author: "Sarah Chen",
    role: "CTO",
    company: "TechFlow",
    industry: "SaaS",
    avatar: "SC",
    rating: 5,
    metrics: {
      implementation: "2 hours",
      userSatisfaction: "+34%",
      supportTickets: "-67%"
    }
  },
  {
    content: "The edge performance is incredible. Sub-30ms verification globally changed our user experience completely. Our conversion rates improved by 23% after switching from our previous provider.",
    author: "Michael Rodriguez",
    role: "Lead Engineer", 
    company: "Commerce Plus",
    industry: "E-commerce",
    avatar: "MR",
    rating: 5,
    metrics: {
      latency: "<30ms",
      conversion: "+23%",
      uptime: "99.99%"
    }
  },
  {
    content: "Plinto's enterprise features are exactly what we needed. SCIM provisioning, custom domains, and dedicated support. Finally, an auth provider that understands enterprise requirements.",
    author: "Jennifer Kim",
    role: "Head of Security",
    company: "FinanceCore",
    industry: "FinTech",
    avatar: "JK",
    rating: 5,
    metrics: {
      compliance: "SOC 2",
      provisioning: "Automated",
      support: "24/7"
    }
  },
  {
    content: "The developer experience is outstanding. TypeScript support, clear docs, and the React hooks make integration a breeze. Our entire team was productive on day one.",
    author: "David Park",
    role: "Senior Developer",
    company: "BuildSpace",
    industry: "Developer Tools",
    avatar: "DP",
    rating: 5,
    metrics: {
      integration: "5 minutes",
      devSatisfaction: "95%",
      maintenance: "Zero"
    }
  },
  {
    content: "Security and compliance are critical for us. Plinto's per-tenant encryption, audit trails, and GDPR compliance give us complete confidence in our authentication layer.",
    author: "Lisa Thompson",
    role: "Compliance Officer",
    company: "HealthTech Solutions",
    industry: "Healthcare",
    avatar: "LT",
    rating: 5,
    metrics: {
      compliance: "HIPAA",
      incidents: "Zero",
      auditReady: "Always"
    }
  },
  {
    content: "Migrating from Auth0 was seamless. Better performance, lower costs, and features that actually work as advertised. Our users noticed the improvement immediately.",
    author: "Alex Johnson",
    role: "VP Engineering",
    company: "EdTech Innovation",
    industry: "Education",
    avatar: "AJ",
    rating: 5,
    metrics: {
      migration: "1 week",
      costSaving: "40%",
      performance: "+2x"
    }
  }
]

const companies = [
  { name: "TechFlow", logo: "TF", color: "bg-blue-500" },
  { name: "Commerce Plus", logo: "CP", color: "bg-green-500" },
  { name: "FinanceCore", logo: "FC", color: "bg-purple-500" },
  { name: "BuildSpace", logo: "BS", color: "bg-orange-500" },
  { name: "HealthTech", logo: "HT", color: "bg-red-500" },
  { name: "EdTech Innovation", logo: "EI", color: "bg-indigo-500" }
]

export function Testimonials() {
  const [ref, inView] = useInView({
    triggerOnce: true,
    threshold: 0.1
  })

  return (
    <section className="py-24" ref={ref}>
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <Badge variant="outline" className="mb-4">
            Customer Stories
          </Badge>
          <h2 className="text-4xl sm:text-5xl font-bold text-gray-900 dark:text-white mb-6">
            Loved by developers,
            <span className="block text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-purple-600 dark:from-blue-400 dark:to-purple-400">
              trusted by enterprises
            </span>
          </h2>
          <p className="text-xl text-gray-600 dark:text-gray-300 max-w-3xl mx-auto">
            See how teams across industries are building better authentication experiences with Plinto.
          </p>
        </motion.div>

        {/* Company logos */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="flex flex-wrap justify-center items-center gap-8 mb-16 opacity-60"
        >
          {companies.map((company, index) => (
            <motion.div
              key={company.name}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={inView ? { opacity: 1, scale: 1 } : {}}
              transition={{ duration: 0.4, delay: 0.3 + index * 0.1 }}
              className="flex items-center gap-3"
            >
              <div className={`w-8 h-8 ${company.color} rounded-lg flex items-center justify-center text-white text-sm font-bold`}>
                {company.logo}
              </div>
              <span className="text-gray-600 dark:text-gray-400 font-medium">
                {company.name}
              </span>
            </motion.div>
          ))}
        </motion.div>

        {/* Testimonials grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 mb-16">
          {testimonials.map((testimonial, index) => (
            <motion.div
              key={testimonial.author}
              initial={{ opacity: 0, y: 20 }}
              animate={inView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.6, delay: index * 0.1 }}
              className="group bg-white dark:bg-gray-900 rounded-2xl p-8 border border-gray-200 dark:border-gray-800 hover:border-blue-300 dark:hover:border-blue-700 hover:shadow-xl transition-all duration-300 relative overflow-hidden"
            >
              {/* Quote icon */}
              <div className="absolute top-6 right-6 opacity-20 group-hover:opacity-30 transition-opacity">
                <Quote className="w-8 h-8 text-blue-500" />
              </div>

              {/* Rating */}
              <div className="flex items-center gap-1 mb-6">
                {[...Array(testimonial.rating)].map((_, i) => (
                  <Star key={i} className="w-4 h-4 text-yellow-400 fill-current" />
                ))}
              </div>

              {/* Content */}
              <blockquote className="text-gray-700 dark:text-gray-300 mb-6 leading-relaxed">
                "{testimonial.content}"
              </blockquote>

              {/* Metrics */}
              <div className="grid grid-cols-3 gap-3 mb-6 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                {Object.entries(testimonial.metrics).map(([key, value]) => (
                  <div key={key} className="text-center">
                    <div className="text-lg font-bold text-gray-900 dark:text-white">
                      {value}
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 capitalize">
                      {key.replace(/([A-Z])/g, ' $1').trim()}
                    </div>
                  </div>
                ))}
              </div>

              {/* Author */}
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 bg-gradient-to-br from-blue-400 to-purple-500 rounded-full flex items-center justify-center text-white font-bold">
                  {testimonial.avatar}
                </div>
                <div>
                  <div className="font-semibold text-gray-900 dark:text-white">
                    {testimonial.author}
                  </div>
                  <div className="text-sm text-gray-600 dark:text-gray-300">
                    {testimonial.role}
                  </div>
                  <div className="text-sm text-gray-500 dark:text-gray-400">
                    {testimonial.company} • {testimonial.industry}
                  </div>
                </div>
              </div>

              {/* Hover effect */}
              <div className="absolute inset-0 bg-gradient-to-br from-blue-50 to-purple-50 dark:from-blue-950/20 dark:to-purple-950/20 opacity-0 group-hover:opacity-100 transition-opacity duration-300 -z-10 rounded-2xl" />
            </motion.div>
          ))}
        </div>

        {/* Social proof stats */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6, delay: 0.8 }}
          className="grid grid-cols-2 md:grid-cols-4 gap-8 mb-16"
        >
          <div className="text-center">
            <div className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
              4.9/5
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-300">
              Average Rating
            </div>
            <div className="flex justify-center mt-2">
              {[...Array(5)].map((_, i) => (
                <Star key={i} className="w-4 h-4 text-yellow-400 fill-current" />
              ))}
            </div>
          </div>

          <div className="text-center">
            <div className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
              500+
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-300">
              Happy Customers
            </div>
          </div>

          <div className="text-center">
            <div className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
              99.9%
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-300">
              Satisfaction Rate
            </div>
          </div>

          <div className="text-center">
            <div className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
              24h
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-300">
              Avg Response Time
            </div>
          </div>
        </motion.div>

        {/* CTA */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6, delay: 1.0 }}
          className="text-center bg-gradient-to-br from-blue-50 to-purple-50 dark:from-blue-950/20 dark:to-purple-950/20 rounded-2xl p-12"
        >
          <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
            Join hundreds of teams building with Plinto
          </h3>
          <p className="text-lg text-gray-600 dark:text-gray-300 mb-8 max-w-2xl mx-auto">
            Start your free trial today and see why developers and enterprises choose Plinto 
            for their authentication infrastructure.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button size="lg" className="text-lg px-8">
              Start Free Trial
              <ArrowRight className="ml-2 w-5 h-5" />
            </Button>
            <Button size="lg" variant="outline" className="text-lg px-8">
              Schedule Demo
            </Button>
          </div>
        </motion.div>
      </div>
    </section>
  )
}