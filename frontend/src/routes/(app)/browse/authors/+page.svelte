<script lang="ts">
  import type { PageData } from './$types';
  let { data }: { data: PageData } = $props();
  let authors = $derived(data.authors);
</script>

<div class="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
  <h1 class="mb-6 text-3xl font-bold tracking-tight">Authors</h1>

  {#if authors.length === 0}
    <p class="py-16 text-center text-muted-foreground">No authors found.</p>
  {:else}
    <div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
      {#each authors as author}
        <a
          href="/browse/authors/{author.id}"
          class="flex items-center justify-between rounded-lg border bg-card p-4 transition-shadow hover:shadow-md"
        >
          <span class="font-medium">{author.name}</span>
          <span class="text-sm text-muted-foreground">{author.book_count} book{author.book_count !== 1 ? 's' : ''}</span>
        </a>
      {/each}
    </div>
  {/if}
</div>
