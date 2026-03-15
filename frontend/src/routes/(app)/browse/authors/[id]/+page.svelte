<script lang="ts">
  import BookGrid from "$lib/components/BookGrid.svelte";
  import type { PageData } from './$types';
  let { data }: { data: PageData } = $props();
</script>

<div class="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
  <div class="mb-6">
    <h1 class="text-3xl font-bold tracking-tight">{data.name}</h1>
    <p class="mt-1 text-muted-foreground">{data.book_count} book{data.book_count !== 1 ? 's' : ''}</p>
  </div>
  <BookGrid books={data.books} />
</div>
