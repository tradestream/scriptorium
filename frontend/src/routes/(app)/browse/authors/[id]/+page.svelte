<script lang="ts">
  import BookGrid from "$lib/components/BookGrid.svelte";
  import { User } from "lucide-svelte";
  import type { PageData } from './$types';
  let { data }: { data: PageData } = $props();
</script>

<div class="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
  <div class="mb-6 flex items-center gap-4">
    {#if data.photo_url}
      <img
        src={data.photo_url}
        alt={data.name}
        class="h-16 w-16 rounded-full object-cover shadow-sm"
      />
    {:else}
      <div class="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
        <User class="h-7 w-7 text-muted-foreground/40" />
      </div>
    {/if}
    <div>
      <h1 class="text-3xl font-bold tracking-tight">{data.name}</h1>
      <p class="mt-1 text-muted-foreground">{data.book_count} book{data.book_count !== 1 ? 's' : ''}</p>
      {#if data.description}
        <p class="mt-2 text-sm text-muted-foreground max-w-2xl">{data.description}</p>
      {/if}
    </div>
  </div>
  <BookGrid books={data.books} />
</div>
