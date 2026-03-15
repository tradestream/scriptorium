<script lang="ts">
  import { goto } from "$app/navigation";
  import { page } from "$app/stores";
  import BookGrid from "$lib/components/BookGrid.svelte";
  import { Input } from "$lib/components/ui/input";
  import { Button } from "$lib/components/ui/button";
  import { Search } from "lucide-svelte";
  import * as api from "$lib/api/client";
  import type { Book } from "$lib/types/index";

  let q = $derived($page.url.searchParams.get('q') ?? '');
  let books = $state<Book[]>([]);
  let total = $state(0);
  let loading = $state(false);
  let searchInput = $state(q);

  async function runSearch(query: string) {
    if (!query.trim()) {
      books = [];
      total = 0;
      return;
    }
    loading = true;
    try {
      const result = await api.searchBooks(query);
      books = result.items;
      total = result.total;
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
</script>

<div class="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
  <h1 class="mb-6 text-3xl font-bold tracking-tight">Search</h1>

  <form onsubmit={handleSubmit} class="mb-8 flex gap-2">
    <div class="relative flex-1">
      <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        bind:value={searchInput}
        placeholder="Search books, authors, descriptions..."
        class="pl-9"
      />
    </div>
    <Button type="submit">Search</Button>
  </form>

  {#if q}
    <p class="mb-4 text-sm text-muted-foreground">
      {#if loading}Searching...{:else}{total} result{total !== 1 ? 's' : ''} for "{q}"{/if}
    </p>
    {#if !loading && books.length > 0}
      <BookGrid {books} />
    {:else if !loading}
      <p class="py-16 text-center text-muted-foreground">No results found.</p>
    {/if}
  {/if}
</div>
