'use client';

import { ThemeProvider } from 'next-themes';
import { FloatingThemeToggle } from '@janua/ui';

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      {children}
      <FloatingThemeToggle />
    </ThemeProvider>
  );
}