<script lang="ts">
  import { Headphones, Search } from 'lucide-svelte';
  import { Input } from '$lib/components/ui/input';
  import { Button } from '$lib/components/ui/button';
  import BookGrid from '$lib/components/BookGrid.svelte';
  import * as api from '$lib/api/client';
  import type { Book } from '$lib/types/index';

  let { data } = $props();
  let absUrl = $derived((data as any).absUrl as string | null ?? null);

  const PAGE_SIZE = 60;
  let books = $state<Book[]>([]);
  let total = $state(0);
  let loading = $state(true);
  let loadingMore = $state(false);
  let skip = $state(0);
  let hasMore = $derived(books.length < total);

  let searchInput = $state('');
  let search = $state('');
  let debounceTimer: ReturnType<typeof setTimeout>;

  function onSearchInput(e: Event) {
    searchInput = (e.target as HTMLInputElement).value;
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => { search = searchInput; }, 300);
  }

  async function load(reset = false) {
    if (reset) { loading = true; skip = 0; }
    else loadingMore = true;

    try {
      let result;
      if (search.trim()) {
        result = await api.searchBooks(search.trim(), {
          skip: reset ? 0 : skip,
          limit: PAGE_SIZE,
        });
        // Client-side filter to only abs-linked from search results
        result = { ...result, items: result.items.filter((b: Book) => b.abs_item_id) };
      } else {
        result = await api.getBooks({
          abs_linked: true,
          skip: reset ? 0 : skip,
          limit: PAGE_SIZE,
          sort_by: 'title',
        });
      }
      books = reset ? result.items : [...books, ...result.items];
      total = result.total;
      skip = (reset ? 0 : skip) + result.items.length;
    } catch (e) {
      console.error(e);
    } finally {
      loading = false;
      loadingMore = false;
    }
  }

  $effect(() => {
    void search;
    load(true);
  });

  function infiniteScroll(node: HTMLElement) {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !loadingMore && hasMore) {
          load(false);
        }
      },
      { rootMargin: '400px' }
    );
    observer.observe(node);
    return { destroy() { observer.disconnect(); } };
  }
</script>

<div class="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
  <div class="mb-6 flex items-center gap-3">
    <Headphones class="h-6 w-6 text-muted-foreground/50" />
    <h1 class="text-2xl font-bold tracking-tight">Audiobooks</h1>
    {#if !loading}
      <span class="ml-auto text-sm text-muted-foreground">{total.toLocaleString()} linked</span>
    {/if}
  </div>

  {#if absUrl}
    <p class="mb-5 text-sm text-muted-foreground">
      Books linked to your <a href={absUrl} target="_blank" rel="noopener noreferrer" class="underline hover:text-foreground">AudiobookShelf</a> instance.
    </p>
  {/if}

  <!-- Search -->
  <div class="mb-6 relative max-w-sm">
    <Search class="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground/50" />
    <Input value={searchInput} oninput={onSearchInput} placeholder="Search audiobooks…" class="h-8 pl-8 text-sm" />
  </div>

  {#if loading}
    <div class="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
      {#each Array(12) as _}
        <div class="aspect-2/3 animate-pulse rounded-md bg-muted"></div>
      {/each}
    </div>
  {:else if books.length === 0}
    <div class="flex flex-col items-center gap-4 py-20 text-center">
      <div class="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
        <Headphones class="h-7 w-7 text-muted-foreground/40" />
      </div>
      <div>
        <p class="font-medium text-foreground">No audiobooks linked yet</p>
        <p class="mt-1 text-sm text-muted-foreground">Import from AudiobookShelf in Settings to link audiobooks.</p>
      </div>
    </div>
  {:else}
    <BookGrid {books} mode="grid" />

    {#if books.length > 0}
      <div class="mt-8 flex flex-col items-center gap-2">
        <p class="text-xs text-muted-foreground tabular-nums">
          Showing {books.length.toLocaleString()} of {total.toLocaleString()}
        </p>
        {#if hasMore}
          <div
            use:infiniteScroll
            class="flex items-center justify-center py-4"
          >
            {#if loadingMore}
              <p class="text-xs text-muted-foreground">Loading…</p>
            {/if}
          </div>
        {/if}
      </div>
    {/if}
  {/if}
</div>
