<script lang="ts">
  import { goto } from "$app/navigation";
  import { page } from "$app/stores";
  import BookGrid from "$lib/components/BookGrid.svelte";
  import { Input } from "$lib/components/ui/input";
  import { Button } from "$lib/components/ui/button";
  // BlurFade removed — motion-sv incompatible with static build
  import { Search, BookOpen, Newspaper, Highlighter, Feather, ExternalLink } from "lucide-svelte";
  import * as api from "$lib/api/client";
  import type { Book } from "$lib/types/index";
  import type { UnifiedSearchResult } from "$lib/api/client";

  let q = $derived($page.url.searchParams.get('q') ?? '');
  let loading = $state(false);
  let searchInput = $state(q);

  // Unified results
  let results = $state<UnifiedSearchResult | null>(null);

  // Book-only results for the grid (fetched separately for full BookRead objects)
  let books = $state<Book[]>([]);
  let bookTotal = $state(0);

  async function runSearch(query: string) {
    if (!query.trim()) {
      results = null;
      books = [];
      bookTotal = 0;
      return;
    }
    loading = true;
    try {
      const [unified, bookResult] = await Promise.all([
        api.unifiedSearch(query, 10),
        api.searchBooks(query, { limit: 12 }),
      ]);
      results = unified;
      books = bookResult.items;
      bookTotal = bookResult.total;
    } catch (err) {
      console.error('Search failed:', err);
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    runSearch(q);
  });

  function handleSubmit(e: SubmitEvent) {
    e.preventDefault();
    goto(`/search?q=${encodeURIComponent(searchInput)}`);
  }

  function coverUrl(book: { id: number; cover_hash?: string | null; cover_format?: string | null }): string {
    if (!book.cover_hash) return '';
    const token = api.getAuthToken();
    const base = `${api.getApiBase()}/books/${book.id}/cover`;
    return token ? `${base}?token=${encodeURIComponent(token)}` : base;
  }
</script>

<div class="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
  <h1 class="mb-6 text-3xl font-bold tracking-tight">Search</h1>

  <form onsubmit={handleSubmit} class="mb-8 flex gap-2">
    <div class="relative flex-1">
      <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        bind:value={searchInput}
        placeholder="Search books, articles, annotations, marginalia..."
        class="pl-9"
      />
    </div>
    <Button type="submit">Search</Button>
  </form>

  {#if q && !loading && results}
    <p class="mb-6 text-sm text-muted-foreground">
      {results.total} result{results.total !== 1 ? 's' : ''} for "{q}"
    </p>

    <!-- Books -->
    {#if books.length > 0}
      <section class="mb-8">
        <div class="flex items-center gap-2 mb-3">
          <BookOpen class="h-4 w-4 text-muted-foreground" />
          <h2 class="text-lg font-semibold">Books</h2>
          <span class="text-xs text-muted-foreground">{bookTotal}</span>
        </div>
        <BookGrid {books} />
      </section>
    {/if}

    <!-- Articles -->
    {#if results.articles.length > 0}
      <section class="mb-8">
        <div class="flex items-center gap-2 mb-3">
          <Newspaper class="h-4 w-4 text-muted-foreground" />
          <h2 class="text-lg font-semibold">Articles</h2>
          <span class="text-xs text-muted-foreground">{results.articles.length}</span>
        </div>
        <div class="divide-y rounded-lg border bg-card overflow-hidden">
          {#each results.articles as a}
            <a href="/articles/{a.id}" class="flex items-center gap-3 px-4 py-2.5 hover:bg-muted/30 transition-colors">
              <div class="min-w-0 flex-1">
                <p class="text-sm font-medium truncate">{a.title}</p>
                <p class="text-xs text-muted-foreground">
                  {a.domain}{#if a.author} · {a.author}{/if}{#if a.progress > 0} · {Math.round(a.progress * 100)}%{/if}
                </p>
              </div>
              <ExternalLink class="h-3.5 w-3.5 shrink-0 text-muted-foreground/30" />
            </a>
          {/each}
        </div>
      </section>
    {/if}

    <!-- Annotations -->
    {#if results.annotations.length > 0}
      <section class="mb-8">
        <div class="flex items-center gap-2 mb-3">
          <Highlighter class="h-4 w-4 text-muted-foreground" />
          <h2 class="text-lg font-semibold">Annotations</h2>
          <span class="text-xs text-muted-foreground">{results.annotations.length}</span>
        </div>
        <div class="space-y-2">
          {#each results.annotations as a}
            <a href="/book/{a.book_id}" class="block rounded-lg border bg-card px-4 py-3 hover:bg-muted/30 transition-colors">
              <p class="text-sm line-clamp-2">{a.content}</p>
              <p class="mt-1 text-xs text-muted-foreground">
                {a.book_title} · <span class="capitalize">{a.annotation_type}</span>
              </p>
            </a>
          {/each}
        </div>
      </section>
    {/if}

    <!-- Marginalia -->
    {#if results.marginalia.length > 0}
      <section class="mb-8">
        <div class="flex items-center gap-2 mb-3">
          <Feather class="h-4 w-4 text-muted-foreground" />
          <h2 class="text-lg font-semibold">Marginalia</h2>
          <span class="text-xs text-muted-foreground">{results.marginalia.length}</span>
        </div>
        <div class="space-y-2">
          {#each results.marginalia as m}
            <a href="/book/{m.book_id}" class="block rounded-lg border bg-card px-4 py-3 hover:bg-muted/30 transition-colors">
              <p class="text-sm line-clamp-2">{m.content}</p>
              <p class="mt-1 text-xs text-muted-foreground">
                {m.book_title} · <span class="capitalize">{m.kind}</span>
              </p>
            </a>
          {/each}
        </div>
      </section>
    {/if}

    <!-- No results -->
    {#if results.total === 0}
      <p class="py-16 text-center text-muted-foreground">No results found.</p>
    {/if}
  {:else if q && loading}
    <p class="text-sm text-muted-foreground">Searching...</p>
  {/if}
</div>
