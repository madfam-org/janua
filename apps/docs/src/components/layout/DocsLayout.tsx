'use client';

import { useState, useEffect } from 'react';
import { usePathname } from 'next/navigation';
import { Menu, X, Search, Moon, Sun, ChevronRight, ChevronDown } from 'lucide-react';
import Link from 'next/link';
import { useTheme } from 'next-themes';
import { cn } from '@/lib/utils';
import { CommandPalette } from '../search/CommandPalette';
import { TableOfContents } from './TableOfContents';
import { AlgoliaSearch } from '../search/AlgoliaSearch';
import { VersionSelector } from '../VersionSelector/VersionSelector';
import { FeedbackWidget } from '../Feedback/FeedbackWidget';

interface NavItem {
  title: string;
  href?: string;
  items?: NavItem[];
  badge?: 'new' | 'beta' | 'deprecated';
}

const navigation: NavItem[] = [
  {
    title: 'Getting Started',
    items: [
      { title: 'Quick Start', href: '/getting-started/quick-start' },
      { title: 'Installation', href: '/getting-started/installation' },
      { title: 'Authentication Basics', href: '/getting-started/auth-basics' },
      { title: 'First App Tutorial', href: '/getting-started/tutorial', badge: 'new' },
    ],
  },
  {
    title: 'Guides',
    items: [
      {
        title: 'Authentication',
        items: [
          { title: 'Email/Password', href: '/guides/auth/email-password' },
          { title: 'Passkeys/WebAuthn', href: '/guides/auth/passkeys', badge: 'beta' },
          { title: 'Social Login', href: '/guides/auth/social' },
          { title: 'Multi-Factor Auth', href: '/guides/auth/mfa' },
        ],
      },
      {
        title: 'Organizations',
        items: [
          { title: 'Creating Organizations', href: '/guides/orgs/create' },
          { title: 'RBAC & Permissions', href: '/guides/orgs/rbac' },
          { title: 'Invitations', href: '/guides/orgs/invitations' },
        ],
      },
      {
        title: 'Sessions',
        items: [
          { title: 'Session Management', href: '/guides/sessions/management' },
          { title: 'Token Refresh', href: '/guides/sessions/refresh' },
          { title: 'Device Management', href: '/guides/sessions/devices' },
        ],
      },
    ],
  },
  {
    title: 'API Reference',
    items: [
      { title: 'Authentication', href: '/api/authentication' },
      { title: 'Users', href: '/api/users' },
      { title: 'Organizations', href: '/api/organizations' },
      { title: 'Sessions', href: '/api/sessions' },
      { title: 'Webhooks', href: '/api/webhooks' },
      { title: 'Admin', href: '/api/admin' },
    ],
  },
  {
    title: 'SDKs',
    items: [
      { title: 'JavaScript/TypeScript', href: '/sdks/javascript', badge: 'new' },
      { title: 'React', href: '/sdks/react' },
      { title: 'Next.js', href: '/sdks/nextjs' },
      { title: 'Python', href: '/sdks/python' },
      { title: 'Go', href: '/sdks/go' },
      { title: 'Flutter', href: '/sdks/flutter' },
    ],
  },
];

function NavItemComponent({ item, depth = 0 }: { item: NavItem; depth?: number }) {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(false);
  const isActive = item.href === pathname;
  const hasChildren = item.items && item.items.length > 0;

  useEffect(() => {
    if (hasChildren && item.items?.some(child => 
      child.href === pathname || 
      child.items?.some(grandchild => grandchild.href === pathname)
    )) {
      setIsOpen(true);
    }
  }, [pathname, hasChildren, item.items]);

  if (hasChildren) {
    return (
      <div>
        <button
          onClick={() => setIsOpen(!isOpen)}
          className={cn(
            'flex w-full items-center justify-between rounded-md px-2 py-1.5 text-sm font-medium transition-colors',
            'hover:bg-gray-100 dark:hover:bg-gray-800',
            depth === 0 && 'font-semibold'
          )}
        >
          <span>{item.title}</span>
          {isOpen ? (
            <ChevronDown className="h-4 w-4 opacity-50" />
          ) : (
            <ChevronRight className="h-4 w-4 opacity-50" />
          )}
        </button>
        {isOpen && (
          <div className={cn('mt-1', depth > 0 && 'ml-4')}>
            {item.items?.map((child, index) => (
              <NavItemComponent key={index} item={child} depth={depth + 1} />
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <Link
      href={item.href || '#'}
      className={cn(
        'flex items-center justify-between rounded-md px-2 py-1.5 text-sm transition-colors',
        'hover:bg-gray-100 dark:hover:bg-gray-800',
        isActive && 'bg-indigo-50 text-indigo-600 dark:bg-indigo-950 dark:text-indigo-400',
        depth > 0 && 'ml-4'
      )}
    >
      <span>{item.title}</span>
      {item.badge && (
        <span
          className={cn(
            'rounded-full px-2 py-0.5 text-xs font-medium uppercase',
            item.badge === 'new' && 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
            item.badge === 'beta' && 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
            item.badge === 'deprecated' && 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'
          )}
        >
          {item.badge}
        </span>
      )}
    </Link>
  );
}

export function DocsLayout({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Keyboard shortcut for search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setSearchOpen(true);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <div className="min-h-screen bg-white dark:bg-gray-950">
      {/* Top Navigation Bar */}
      <header className="sticky top-0 z-40 w-full border-b border-gray-200 bg-white/80 backdrop-blur dark:border-gray-800 dark:bg-gray-950/80">
        <div className="flex h-16 items-center px-4 sm:px-6 lg:px-8">
          {/* Mobile menu button */}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="mr-4 rounded-md p-2 text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800 lg:hidden"
          >
            {sidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>

          {/* Logo */}
          <Link href="/" className="flex items-center space-x-2">
            <span className="text-xl font-bold text-indigo-600 dark:text-indigo-400">Janua</span>
            <span className="text-sm text-gray-500 dark:text-gray-400">Docs</span>
          </Link>

          {/* Center spacer */}
          <div className="flex-1" />

          {/* Right side actions */}
          <div className="flex items-center space-x-4">
            {/* Version Selector */}
            <VersionSelector />

            {/* Search - Algolia or Command Palette based on env */}
            {process.env.NEXT_PUBLIC_ALGOLIA_APP_ID ? (
              <AlgoliaSearch />
            ) : (
              <button
                onClick={() => setSearchOpen(true)}
                className="flex items-center space-x-2 rounded-md bg-gray-100 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700"
              >
                <Search className="h-4 w-4" />
                <span className="hidden sm:inline">Search</span>
                <kbd className="hidden rounded bg-gray-200 px-1.5 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-700 dark:text-gray-400 sm:inline">
                  ⌘K
                </kbd>
              </button>
            )}

            {/* Theme toggle */}
            {mounted && (
              <button
                onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
                className="rounded-md p-2 text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
              >
                {theme === 'dark' ? (
                  <Sun className="h-5 w-5" />
                ) : (
                  <Moon className="h-5 w-5" />
                )}
              </button>
            )}

            {/* GitHub link */}
            <a
              href="https://github.com/madfam-io/janua"
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-md p-2 text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
            >
              <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
              </svg>
            </a>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="mx-auto max-w-8xl">
        <div className="flex">
          {/* Left Sidebar - Navigation */}
          <aside
            className={cn(
              'fixed inset-y-0 left-0 z-30 w-64 transform overflow-y-auto border-r border-gray-200 bg-white pt-16 transition-transform dark:border-gray-800 dark:bg-gray-950 lg:static lg:block lg:transform-none',
              sidebarOpen ? 'translate-x-0' : '-translate-x-full'
            )}
          >
            <nav className="space-y-1 p-4">
              {navigation.map((section, index) => (
                <div key={index} className="mb-4">
                  <NavItemComponent item={section} />
                </div>
              ))}
            </nav>
          </aside>

          {/* Center Content */}
          <main className="min-w-0 flex-1 px-4 py-8 sm:px-6 lg:px-8">
            <article className="prose prose-gray mx-auto max-w-none dark:prose-invert prose-headings:scroll-mt-20 prose-code:rounded-md prose-code:bg-gray-100 prose-code:px-1 prose-code:py-0.5 prose-code:text-gray-800 prose-code:before:content-[''] prose-code:after:content-[''] dark:prose-code:bg-gray-800 dark:prose-code:text-gray-200">
              {children}
            </article>
          </main>

          {/* Right Sidebar - Table of Contents */}
          <aside className="hidden w-64 shrink-0 xl:block">
            <div className="sticky top-20 p-4">
              <TableOfContents />
            </div>
          </aside>
        </div>
      </div>

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Command Palette */}
      <CommandPalette open={searchOpen} onClose={() => setSearchOpen(false)} />

      {/* Feedback Widget */}
      <FeedbackWidget />
    </div>
  );
}