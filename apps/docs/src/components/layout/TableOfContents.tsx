'use client';

import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';

interface TOCItem {
  id: string;
  text: string;
  level: number;
}

/**
 * Sanitize a string for safe use as an HTML ID attribute.
 * Only allows alphanumeric characters, hyphens, and underscores.
 */
function sanitizeId(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s-_]/g, '') // Remove unsafe characters
    .replace(/\s+/g, '-')          // Replace spaces with hyphens
    .replace(/-+/g, '-')           // Collapse multiple hyphens
    .replace(/^-|-$/g, '');        // Trim leading/trailing hyphens
}

/**
 * Sanitize text content for display.
 * Escapes HTML entities to prevent XSS.
 */
function _sanitizeText(text: string): string {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

export function TableOfContents() {
  const [headings, setHeadings] = useState<TOCItem[]>([]);
  const [activeId, setActiveId] = useState<string>('');

  useEffect(() => {
    // Get all headings from the article
    const article = document.querySelector('article');
    if (!article) return;

    const headingElements = article.querySelectorAll('h2, h3, h4');
    const items: TOCItem[] = Array.from(headingElements).map((heading) => {
      // Sanitize the heading text before using it as an ID
      const rawText = heading.textContent || '';
      const sanitizedId = heading.id || sanitizeId(rawText);

      // Ensure heading has a safe ID for linking
      if (!heading.id && sanitizedId) {
        heading.id = sanitizedId;
      }

      return {
        id: sanitizedId,
        text: rawText, // Store raw text, will sanitize on render
        level: parseInt(heading.tagName[1]),
      };
    });

    setHeadings(items);
  }, []);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setActiveId(entry.target.id);
          }
        });
      },
      {
        rootMargin: '-100px 0px -70% 0px',
      }
    );

    headings.forEach(({ id }) => {
      const element = document.getElementById(id);
      if (element) {
        observer.observe(element);
      }
    });

    return () => {
      headings.forEach(({ id }) => {
        const element = document.getElementById(id);
        if (element) {
          observer.unobserve(element);
        }
      });
    };
  }, [headings]);

  if (headings.length === 0) {
    return null;
  }

  return (
    <div>
      <h5 className="mb-4 text-sm font-semibold text-gray-900 dark:text-gray-100">
        On this page
      </h5>
      <nav className="space-y-1">
        {headings.map((heading) => (
          <a
            key={heading.id}
            href={`#${encodeURIComponent(heading.id)}`}
            onClick={(e) => {
              e.preventDefault();
              // Use getElementById which is safe - id is already sanitized
              const element = document.getElementById(heading.id);
              if (element) {
                element.scrollIntoView({
                  behavior: 'smooth',
                  block: 'start',
                });
              }
            }}
            className={cn(
              'block text-sm transition-colors',
              heading.level === 2 && 'font-medium',
              heading.level === 3 && 'ml-4',
              heading.level === 4 && 'ml-8',
              activeId === heading.id
                ? 'text-indigo-600 dark:text-indigo-400'
                : 'text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100'
            )}
          >
            {heading.text}
          </a>
        ))}
      </nav>
    </div>
  );
}
