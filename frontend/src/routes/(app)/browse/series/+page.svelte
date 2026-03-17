<script lang="ts">
  import { BookOpen, Layers, Search } from 'lucide-svelte';
  import * as api from '$lib/api/client';
  import type { SeriesDetail } from '$lib/types/index';

  let { data } = $props();

  let allSeries = $state(data.series as SeriesDetail[]);
  let libraries = $derived(data.libraries as { id: number; name: string }[]);
  let selectedLibrary = $state<number | null>(null);
  let searchQuery = $state('');
  let loading = $state(false);

  // Filter series client-side by search query
  let filtered = $derived(
    searchQuery.trim()
      ? allSeries.filter(s => s.name.toLowerCase().includes(searchQuery.toLowerCase()))
      : allSeries
  );

  async function selectLibrary(libraryId: number | null) {
    selectedLibrary = libraryId;
    loading = true;
    try {
      allSeries = await api.getAllSeries(0, 500, libraryId ? { library_id: libraryId } : undefined);
    } catch { /* keep current */ }
    loading = false;
  }

  function coverUrl(s: SeriesDetail): string {
    if (!s.cover_book_id) return '';
    const token = api.getAuthToken();
    const base = `${api.getApiBase()}/books/${s.cover_book_id}/cover`;
    return token ? `${base}?token=${encodeURIComponent(token)}` : base;
  }
</script>

<div class="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
  <div class="mb-6 flex items-center gap-3">
    <Layers class="h-6 w-6 text-muted-foreground/50" />
    <h1 class="text-2xl font-bold tracking-tight">Series</h1>
    <span class="ml-auto text-sm text-muted-foreground">{filtered.length} series</span>
  </div>

  <!-- Filter bar -->
  <div class="mb-6 flex flex-wrap items-center gap-2">
    <!-- Library filter tabs -->
    <div class="flex items-center gap-1 rounded-md border bg-background px-1.5 py-1">
      <button
        onclick={() => selectLibrary(null)}
        class="rounded px-2.5 py-1 text-xs transition-colors {selectedLibrary === null ? 'bg-foreground/10 text-foreground font-medium' : 'text-muted-foreground hover:text-foreground'}"
      >All</button>
      {#each libraries as lib}
        <button
          onclick={() => selectLibrary(lib.id)}
          class="rounded px-2.5 py-1 text-xs transition-colors {selectedLibrary === lib.id ? 'bg-foreground/10 text-foreground font-medium' : 'text-muted-foreground hover:text-foreground'}"
        >{lib.name}</button>
      {/each}
    </div>

    <!-- Search -->
    <div class="relative min-w-0 flex-1 sm:max-w-xs">
      <Search class="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground/50" />
      <input
        type="text"
        bind:value={searchQuery}
        placeholder="Filter series…"
        class="h-8 w-full rounded-md border bg-background pl-8 pr-3 text-sm outline-none focus:ring-1 focus:ring-ring"
      />
    </div>
  </div>

  {#if loading}
    <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {#each Array(8) as _}
        <div class="h-19 animate-pulse rounded-lg bg-muted"></div>
      {/each}
    </div>
  {:else if filtered.length === 0}
    <div class="flex flex-col items-center gap-4 py-20 text-center">
      <div class="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
        <Layers class="h-7 w-7 text-muted-foreground/40" />
      </div>
      <div>
        <p class="font-medium text-foreground">
          {searchQuery ? 'No series match your search' : 'No series found'}
        </p>
        <p class="mt-1 text-sm text-muted-foreground">
          {searchQuery ? 'Try a different search term' : 'Series are created automatically when books share a series name.'}
        </p>
      </div>
    </div>
  {:else}
    <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {#each filtered as s}
        {@const cover = coverUrl(s)}
        <a
          href="/browse/series/{s.id}"
          class="group flex gap-3 rounded-lg border bg-card p-3 transition-shadow hover:shadow-md"
        >
          <div class="relative h-16 w-11 shrink-0">
            {#if cover}
              <img src={cover} alt="" class="h-full w-full rounded object-cover shadow-sm" loading="lazy" />
            {:else}
              <div class="flex h-full w-full items-center justify-center rounded bg-muted">
                <BookOpen class="h-4 w-4 text-muted-foreground/30" />
              </div>
            {/if}
          </div>

          <div class="min-w-0 flex-1">
            <p class="truncate text-sm font-semibold transition-colors group-hover:text-primary">{s.name}</p>
            {#if s.description}
              <p class="mt-0.5 line-clamp-1 text-xs text-muted-foreground">{s.description}</p>
            {/if}
            <p class="mt-1 text-xs text-muted-foreground/60">
              {s.book_count} {s.book_count === 1 ? 'entry' : 'entries'}
            </p>
          </div>
        </a>
      {/each}
    </div>
  {/if}
</div>
