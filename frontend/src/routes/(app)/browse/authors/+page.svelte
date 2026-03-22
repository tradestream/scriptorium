<script lang="ts">
  import { Input } from '$lib/components/ui/input';
  import { BookOpen, Search, ArrowUpDown } from 'lucide-svelte';
  import type { PageData } from './$types';
  let { data }: { data: PageData } = $props();
  let allAuthors = $derived(data.authors);

  let filterText = $state('');
  let sortBy = $state<'name' | 'count'>('name');

  let filtered = $derived(() => {
    let list = filterText
      ? allAuthors.filter(a => a.name.toLowerCase().includes(filterText.toLowerCase()))
      : allAuthors;
    if (sortBy === 'count') {
      list = [...list].sort((a, b) => b.book_count - a.book_count);
    }
    return list;
  });

  let totalBooks = $derived(allAuthors.reduce((sum, a) => sum + a.book_count, 0));
</script>

<div class="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
  <div class="mb-6 flex items-end justify-between gap-4">
    <div>
      <h1 class="text-3xl font-bold tracking-tight">Authors</h1>
      <p class="mt-1 text-sm text-muted-foreground">{allAuthors.length} authors, {totalBooks} books</p>
    </div>
    <div class="flex items-center gap-2">
      <div class="relative">
        <Search class="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground/50" />
        <Input placeholder="Filter authors…" bind:value={filterText} class="pl-8 w-56 h-8 text-sm" />
      </div>
      <button
        onclick={() => sortBy = sortBy === 'name' ? 'count' : 'name'}
        class="flex h-8 items-center gap-1.5 rounded-md border bg-background px-2.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        title="Sort by {sortBy === 'name' ? 'book count' : 'name'}"
      >
        <ArrowUpDown class="h-3.5 w-3.5" />
        <span class="hidden sm:inline">{sortBy === 'name' ? 'A-Z' : 'Count'}</span>
      </button>
    </div>
  </div>

  {#if filtered().length === 0}
    <p class="py-16 text-center text-muted-foreground">No authors found.</p>
  {:else}
    <div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
      {#each filtered() as author (author.id)}
        <a
          href="/browse/authors/{author.id}"
          class="group flex items-center gap-3 rounded-lg border bg-card px-4 py-3 transition-all hover:shadow-md hover:border-border/80"
        >
          <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
            <span class="text-sm font-bold tabular-nums">{author.book_count}</span>
          </div>
          <div class="min-w-0 flex-1">
            <p class="font-medium truncate group-hover:text-foreground/80">{author.name}</p>
            <p class="text-xs text-muted-foreground">{author.book_count} {author.book_count === 1 ? 'book' : 'books'}</p>
          </div>
        </a>
      {/each}
    </div>
  {/if}
</div>
