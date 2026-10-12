import React from 'react'
import { render, screen } from '@testing-library/react'
import { CTASection } from './cta'
import { HonestHeroSection } from './honest-hero'
import { LandingCTA } from './landing-cta'
import { SITE_LINKS } from '@/lib/site-links'

// Regression for money-engine journeys J1 F7 (2026-10-11): the landing CTAs
// pointed at demo.janua.dev (no DNS), docs.janua.dev/self-hosting (404) and
// the madfam-io GitHub account (only a rename redirect).
const DEAD_TARGETS = ['demo.janua.dev', 'docs.janua.dev/self-hosting', 'github.com/madfam-io/']

function allHrefs(container: HTMLElement): string[] {
  return Array.from(container.querySelectorAll('a')).map((a) => a.getAttribute('href') ?? '')
}

describe('marketing CTA links', () => {
  it('"Schedule a demo" opens the on-site auth playground', () => {
    render(<CTASection />)
    expect(screen.getByText('Schedule a demo').closest('a')?.getAttribute('href')).toBe('/demo')
  })

  it('"Start self-hosting" opens the README self-hosting guide', () => {
    const hero = render(<HonestHeroSection />)
    const cta = render(<LandingCTA />)
    for (const view of [hero, cta]) {
      const link = Array.from(view.container.querySelectorAll('a')).find((a) =>
        a.textContent?.includes('Start self-hosting'),
      )
      expect(link?.getAttribute('href')).toBe(
        'https://github.com/madfam-org/janua#self-hosting-production',
      )
    }
  })

  it('no CTA points at a known-dead target', () => {
    for (const Section of [CTASection, HonestHeroSection, LandingCTA]) {
      const { container, unmount } = render(<Section />)
      for (const href of allHrefs(container)) {
        for (const dead of DEAD_TARGETS) {
          expect(href).not.toContain(dead)
        }
      }
      unmount()
    }
  })

  it('every GitHub link uses the madfam-org org', () => {
    for (const href of Object.values(SITE_LINKS)) {
      if (href.includes('github.com')) {
        expect(href.startsWith('https://github.com/madfam-org/janua')).toBe(true)
      }
    }
  })
})
