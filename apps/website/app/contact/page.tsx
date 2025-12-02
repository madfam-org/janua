import { Metadata } from 'next'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { ArrowRight, Mail, MessageCircle, Phone, MapPin, Clock, Users } from 'lucide-react'

export const metadata: Metadata = {
  title: 'Contact Us | Janua',
  description: 'Get in touch with the Janua team. Sales inquiries, technical support, partnerships, and general questions.',
}

export default function ContactPage() {
  return (
    <div className="min-h-screen bg-white dark:bg-slate-950">
      {/* Hero Section */}
      <section className="relative pt-32 pb-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-4xl mx-auto">
            <h1 className="text-5xl font-bold tracking-tight text-slate-900 dark:text-white mb-8">
              Get in{' '}
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-cyan-600">
                Touch
              </span>
            </h1>
            <p className="text-xl text-slate-600 dark:text-slate-300 mb-10">
              Have questions about Janua? We're here to help with sales, technical support, partnerships, and more.
            </p>
          </div>
        </div>
      </section>

      {/* Contact Options */}
      <section className="py-20 bg-slate-50 dark:bg-slate-900/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            <div className="bg-white dark:bg-slate-800 rounded-lg p-6 border border-slate-200 dark:border-slate-700">
              <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/20 rounded-lg flex items-center justify-center mb-4">
                <Users className="w-6 h-6 text-blue-600 dark:text-blue-400" />
              </div>
              <h3 className="text-xl font-semibold text-slate-900 dark:text-white mb-2">
                Sales & Enterprise
              </h3>
              <p className="text-slate-600 dark:text-slate-400 mb-4">
                Interested in Janua for your organization? Let's discuss your authentication needs.
              </p>
              <Button className="w-full group" asChild>
                <Link href="mailto:sales@janua.dev">
                  Contact Sales
                  <ArrowRight className="ml-2 w-4 h-4 transition-transform group-hover:translate-x-1" />
                </Link>
              </Button>
            </div>

            <div className="bg-white dark:bg-slate-800 rounded-lg p-6 border border-slate-200 dark:border-slate-700">
              <div className="w-12 h-12 bg-green-100 dark:bg-green-900/20 rounded-lg flex items-center justify-center mb-4">
                <MessageCircle className="w-6 h-6 text-green-600 dark:text-green-400" />
              </div>
              <h3 className="text-xl font-semibold text-slate-900 dark:text-white mb-2">
                Technical Support
              </h3>
              <p className="text-slate-600 dark:text-slate-400 mb-4">
                Need help with integration or have technical questions? Our team is here to assist.
              </p>
              <Button className="w-full group" asChild>
                <Link href="mailto:support@janua.dev">
                  Get Support
                  <ArrowRight className="ml-2 w-4 h-4 transition-transform group-hover:translate-x-1" />
                </Link>
              </Button>
            </div>

            <div className="bg-white dark:bg-slate-800 rounded-lg p-6 border border-slate-200 dark:border-slate-700">
              <div className="w-12 h-12 bg-purple-100 dark:bg-purple-900/20 rounded-lg flex items-center justify-center mb-4">
                <Mail className="w-6 h-6 text-purple-600 dark:text-purple-400" />
              </div>
              <h3 className="text-xl font-semibold text-slate-900 dark:text-white mb-2">
                General Inquiries
              </h3>
              <p className="text-slate-600 dark:text-slate-400 mb-4">
                Questions about partnerships, press, or anything else? We'd love to hear from you.
              </p>
              <Button className="w-full group" asChild>
                <Link href="mailto:hello@janua.dev">
                  Say Hello
                  <ArrowRight className="ml-2 w-4 h-4 transition-transform group-hover:translate-x-1" />
                </Link>
              </Button>
            </div>
          </div>
        </div>
      </section>

      {/* Specialized Contact */}
      <section className="py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold text-slate-900 dark:text-white mb-4">
              Specialized Inquiries
            </h2>
            <p className="text-lg text-slate-600 dark:text-slate-300">
              Looking for something specific? We have dedicated teams for specialized needs.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div className="space-y-6">
              <div className="flex gap-4">
                <div className="w-12 h-12 bg-amber-100 dark:bg-amber-900/20 rounded-lg flex items-center justify-center flex-shrink-0">
                  <Users className="w-6 h-6 text-amber-600 dark:text-amber-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Healthcare & HIPAA</h3>
                  <p className="text-slate-600 dark:text-slate-400 mb-2">
                    Specialized support for healthcare organizations requiring HIPAA compliance.
                  </p>
                  <Link href="mailto:healthcare@janua.dev" className="text-blue-600 dark:text-blue-400 hover:underline">
                    healthcare@janua.dev
                  </Link>
                </div>
              </div>

              <div className="flex gap-4">
                <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/20 rounded-lg flex items-center justify-center flex-shrink-0">
                  <MapPin className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Enterprise Solutions</h3>
                  <p className="text-slate-600 dark:text-slate-400 mb-2">
                    Large-scale deployments, custom SLAs, and enterprise-specific requirements.
                  </p>
                  <Link href="mailto:enterprise@janua.dev" className="text-blue-600 dark:text-blue-400 hover:underline">
                    enterprise@janua.dev
                  </Link>
                </div>
              </div>

              <div className="flex gap-4">
                <div className="w-12 h-12 bg-green-100 dark:bg-green-900/20 rounded-lg flex items-center justify-center flex-shrink-0">
                  <Users className="w-6 h-6 text-green-600 dark:text-green-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Careers & Talent</h3>
                  <p className="text-slate-600 dark:text-slate-400 mb-2">
                    Interested in joining our team? View open positions and submit applications.
                  </p>
                  <Link href="mailto:careers@janua.dev" className="text-blue-600 dark:text-blue-400 hover:underline">
                    careers@janua.dev
                  </Link>
                </div>
              </div>
            </div>

            <div className="bg-gradient-to-br from-blue-50 to-cyan-50 dark:from-slate-800 dark:to-slate-700 rounded-lg p-8">
              <h3 className="text-2xl font-bold text-slate-900 dark:text-white mb-4">
                Quick Response Times
              </h3>
              <div className="space-y-4">
                <div className="flex items-center gap-3">
                  <Clock className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                  <div>
                    <div className="font-medium text-slate-900 dark:text-white">Sales Inquiries</div>
                    <div className="text-sm text-slate-600 dark:text-slate-400">Within 4 hours</div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Clock className="w-5 h-5 text-green-600 dark:text-green-400" />
                  <div>
                    <div className="font-medium text-slate-900 dark:text-white">Technical Support</div>
                    <div className="text-sm text-slate-600 dark:text-slate-400">Within 24 hours</div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Clock className="w-5 h-5 text-purple-600 dark:text-purple-400" />
                  <div>
                    <div className="font-medium text-slate-900 dark:text-white">General Inquiries</div>
                    <div className="text-sm text-slate-600 dark:text-slate-400">Within 48 hours</div>
                  </div>
                </div>
              </div>
              
              <div className="mt-6 pt-6 border-t border-slate-200 dark:border-slate-600">
                <p className="text-sm text-slate-600 dark:text-slate-400">
                  For immediate technical assistance, check our{' '}
                  <Link href="https://docs.janua.dev" className="text-blue-600 dark:text-blue-400 hover:underline">
                    documentation
                  </Link>{' '}
                  or join our developer Discord.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Alternative Contact Methods */}
      <section className="py-20 bg-slate-50 dark:bg-slate-900/50">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl font-bold text-slate-900 dark:text-white mb-6">
            Other Ways to Connect
          </h2>
          <p className="text-lg text-slate-600 dark:text-slate-300 mb-10">
            Join our community and stay updated with the latest from Janua.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button variant="outline" className="group" asChild>
              <Link href="https://github.com/madfam-io/janua" target="_blank" rel="noopener">
                GitHub Community
                <ArrowRight className="ml-2 w-4 h-4 transition-transform group-hover:translate-x-1" />
              </Link>
            </Button>

            <Button variant="outline" className="group" asChild>
              <Link href="https://docs.janua.dev" target="_blank" rel="noopener">
                Documentation
                <ArrowRight className="ml-2 w-4 h-4 transition-transform group-hover:translate-x-1" />
              </Link>
            </Button>

            <Button variant="outline" className="group" asChild>
              <Link href="/blog">
                Developer Blog
                <ArrowRight className="ml-2 w-4 h-4 transition-transform group-hover:translate-x-1" />
              </Link>
            </Button>
          </div>
        </div>
      </section>
    </div>
  )
}