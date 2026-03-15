<script lang="ts">
  import BookGrid from "$lib/components/BookGrid.svelte";
  import { Button } from "$lib/components/ui/button";
  import { ArrowLeft, Trash2 } from "lucide-svelte";
  import * as api from "$lib/api/client";
  import type { CollectionDetail } from "$lib/types/index";
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();
  let collection = $state<CollectionDetail | null>(data.collection ?? null);

  async function removeBook(bookId: number) {
    if (!collection) return;
    await api.removeBookFromCollection(collection.id, bookId);
    collection = { ...collection, books: collection.books.filter(b => b.id !== bookId), book_count: collection.book_count - 1 };
  }
</script>

<div class="flex h-full flex-col">
  {#if !collection}
    <div class="flex flex-1 items-center justify-center text-muted-foreground">Collection not found</div>
  {:else}
    <div class="border-b px-6 py-5">
      <div class="flex items-center gap-3">
        <Button variant="ghost" size="icon" href="/collections" class="h-8 w-8 shrink-0">
          <ArrowLeft class="h-4 w-4" />
        </Button>
        <div class="min-w-0">
          <h1 class="font-serif text-2xl font-semibold tracking-tight truncate">{collection.name}</h1>
          {#if collection.description}
            <p class="mt-0.5 text-sm text-muted-foreground">{collection.description}</p>
          {/if}
          <p class="mt-1 text-xs tabular-nums text-muted-foreground/60">{collection.book_count} book{collection.book_count !== 1 ? 's' : ''}</p>
        </div>
      </div>
    </div>

    <div class="flex-1 overflow-y-auto px-6 py-6">
      {#if collection.books.length === 0}
        <div class="flex flex-col items-center justify-center py-16 text-center">
          <p class="text-muted-foreground">No books in this collection yet.</p>
          <p class="mt-1 text-sm text-muted-foreground/70">Add books from their detail pages.</p>
        </div>
      {:else}
        <BookGrid books={collection.books} mode="grid" />
      {/if}
    </div>
  {/if}
</div>
