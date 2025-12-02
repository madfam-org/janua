'use client';

import React, { useState, useRef, useEffect } from 'react';
import algoliasearch from 'algoliasearch/lite';
import { InstantSearch, SearchBox, Hits, Highlight, Configure, useInstantSearch } from 'react-instantsearch';
import { Dialog, DialogContent } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Search, FileText, Hash, Code, BookOpen, ArrowRight, Loader2 } from 'lucide-react';
import { useRouter } from 'next/navigation';

// Initialize Algolia client
const searchClient = algoliasearch(
  process.env.NEXT_PUBLIC_ALGOLIA_APP_ID || 'YOUR_APP_ID',
  process.env.NEXT_PUBLIC_ALGOLIA_SEARCH_KEY || 'YOUR_SEARCH_KEY'
);

interface AlgoliaSearchProps {
  indexName?: string;
  placeholder?: string;
  className?: string;
}

interface HitProps {
  hit: any;
}

// Custom Hit component
function Hit({ hit }: HitProps) {
  const router = useRouter();

  const getIcon = () => {
    switch (hit.type) {
      case 'api':
        return <Code className="h-4 w-4" />;
      case 'guide':
        return <BookOpen className="h-4 w-4" />;
      case 'reference':
        return <Hash className="h-4 w-4" />;
      default:
        return <FileText className="h-4 w-4" />;
    }
  };

  const getTypeBadge = () => {
    const variants: Record<string, any> = {
      api: 'default',
      guide: 'secondary',
      reference: 'outline',
      page: 'ghost'
    };

    return (
      <Badge variant={variants[hit.type] || 'ghost'} className="text-xs">
        {hit.type}
      </Badge>
    );
  };

  return (
    <button
      onClick={() => router.push(hit.url)}
      className="w-full text-left p-3 hover:bg-muted/50 rounded-lg transition-colors group"
    >
      <div className="flex items-start gap-3">
        <div className="mt-1 text-muted-foreground">{getIcon()}</div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-medium text-sm truncate">
              <Highlight attribute="title" hit={hit} />
            </h3>
            {getTypeBadge()}
          </div>

          {hit.hierarchy && (
            <div className="flex items-center gap-1 text-xs text-muted-foreground mb-1">
              {hit.hierarchy.lvl0 && <span>{hit.hierarchy.lvl0}</span>}
              {hit.hierarchy.lvl1 && (
                <>
                  <ArrowRight className="h-3 w-3" />
                  <span>{hit.hierarchy.lvl1}</span>
                </>
              )}
              {hit.hierarchy.lvl2 && (
                <>
                  <ArrowRight className="h-3 w-3" />
                  <span>{hit.hierarchy.lvl2}</span>
                </>
              )}
            </div>
          )}

          <p className="text-sm text-muted-foreground line-clamp-2">
            <Highlight attribute="content" hit={hit} />
          </p>
        </div>
      </div>
    </button>
  );
}

// Search state indicator
function SearchStateIndicator() {
  const { status } = useInstantSearch();

  if (status === 'loading' || status === 'stalled') {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return null;
}

// No results component
function NoResults() {
  const { indexUiState } = useInstantSearch();

  if (indexUiState.query && indexUiState.query.length > 0) {
    return (
      <div className="text-center py-8">
        <p className="text-muted-foreground">
          No results found for "<strong>{indexUiState.query}</strong>"
        </p>
        <p className="text-sm text-muted-foreground mt-2">
          Try searching with different keywords
        </p>
      </div>
    );
  }

  return null;
}

// Custom SearchBox with better styling
function CustomSearchBox() {
  return (
    <SearchBox
      placeholder="Search documentation..."
      classNames={{
        root: 'relative',
        form: 'relative',
        input: 'w-full px-10 py-3 bg-background border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent',
        submit: 'absolute left-3 top-1/2 -translate-y-1/2',
        reset: 'absolute right-3 top-1/2 -translate-y-1/2',
        submitIcon: 'h-4 w-4 text-muted-foreground',
        resetIcon: 'h-4 w-4 text-muted-foreground hover:text-foreground'
      }}
      submitIconComponent={() => <Search className="h-4 w-4" />}
    />
  );
}

export function AlgoliaSearch({
  indexName = 'docs',
  placeholder = 'Search documentation...',
  className = ''
}: AlgoliaSearchProps) {
  const [isOpen, setIsOpen] = useState(false);
  const searchButtonRef = useRef<HTMLButtonElement>(null);

  // Keyboard shortcut
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsOpen(true);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <>
      {/* Search trigger button */}
      <button
        ref={searchButtonRef}
        onClick={() => setIsOpen(true)}
        className={`flex items-center gap-2 px-3 py-2 text-sm text-muted-foreground bg-muted/50 hover:bg-muted rounded-lg transition-colors ${className}`}
      >
        <Search className="h-4 w-4" />
        <span>{placeholder}</span>
        <kbd className="hidden sm:inline-flex h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium opacity-100">
          <span className="text-xs">⌘</span>K
        </kbd>
      </button>

      {/* Search modal */}
      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent className="max-w-2xl p-0 gap-0">
          <InstantSearch searchClient={searchClient} indexName={indexName}>
            <div className="border-b p-4">
              <CustomSearchBox />
            </div>

            <div className="max-h-[60vh] overflow-y-auto p-4">
              {/* @ts-expect-error - hitsPerPage is valid in react-instantsearch */}
              <Configure hitsPerPage={20} />
              <SearchStateIndicator />
              <Hits hitComponent={Hit} classNames={{ list: 'space-y-1' }} />
              <NoResults />
            </div>
          </InstantSearch>
        </DialogContent>
      </Dialog>
    </>
  );
}

// Inline search for mobile or compact layouts
export function InlineAlgoliaSearch({
  indexName = 'docs',
  placeholder = 'Search...',
  className = ''
}: AlgoliaSearchProps) {
  const [_query, _setQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);

  return (
    <div className={`relative ${className}`}>
      <InstantSearch searchClient={searchClient} indexName={indexName}>
        <div className="relative">
          <SearchBox
            placeholder={placeholder}
            onFocus={() => setIsSearching(true)}
            classNames={{
              root: 'relative',
              form: 'relative',
              input: 'w-full px-10 py-2 bg-background border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary',
              submit: 'absolute left-3 top-1/2 -translate-y-1/2',
              reset: 'absolute right-3 top-1/2 -translate-y-1/2',
              submitIcon: 'h-4 w-4 text-muted-foreground',
              resetIcon: 'h-4 w-4 text-muted-foreground'
            }}
            submitIconComponent={() => <Search className="h-4 w-4" />}
          />
        </div>

        {isSearching && (
          <div className="absolute top-full left-0 right-0 mt-2 bg-background border rounded-lg shadow-lg z-50 max-h-96 overflow-y-auto">
            <div className="p-2">
              {/* @ts-expect-error - hitsPerPage is valid in react-instantsearch */}
            <Configure hitsPerPage={10} />
              <SearchStateIndicator />
              <Hits hitComponent={Hit} classNames={{ list: 'space-y-1' }} />
              <NoResults />
            </div>
          </div>
        )}
      </InstantSearch>

      {isSearching && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setIsSearching(false)}
        />
      )}
    </div>
  );
}