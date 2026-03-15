<script lang="ts">
  import { BookOpen, Layers } from 'lucide-svelte';
  import * as api from '$lib/api/client';
  import type { SeriesDetail } from '$lib/types/index';

  let { data } = $props();
  let series = $derived(data.series as SeriesDetail[]);

  function coverUrl(s: SeriesDetail): string {
    if (!s.cover_book_id) return '';
    const token = api.getAuthToken();
    const base = `${api.getApiBase()}/books/${s.cover_book_id}/cover`;
    return token ? `${base}?token=${encodeURIComponent(token)}` : base;
  }
</script>

<div class="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
  <div class="mb-8 flex items-center gap-3">
    <Layers class="h-6 w-6 text-muted-foreground/50" />
    <h1 class="text-2xl font-bold tracking-tight">Series</h1>
    <span class="ml-auto text-sm text-muted-foreground">{series.length} series</span>
  </div>

  {#if series.length === 0}
    <div class="flex flex-col items-center gap-4 py-20 text-center">
      <div class="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
        <Layers class="h-7 w-7 text-muted-foreground/40" />
      </div>
      <div>
        <p class="font-medium text-foreground">No series yet</p>
        <p class="mt-1 text-sm text-muted-foreground">Series are created automatically when books share a series name.</p>
      </div>
    </div>
  {:else}
    <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {#each series as s}
        {@const cover = coverUrl(s)}
        <a
          href="/browse/series/{s.id}"
          class="group flex gap-3 rounded-lg border bg-card p-3 transition-shadow hover:shadow-md"
        >
          <!-- Cover thumbnail -->
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
