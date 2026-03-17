<script lang="ts">
  import BookCard from "./BookCard.svelte";
  import { BookOpen, Headphones, Check } from "lucide-svelte";
  import { bookCoverUrl } from "$lib/api/client";
  import { cn } from "$lib/utils/cn";
  import type { Book } from "$lib/types/index";

  interface Props {
    books: Book[];
    mode?: 'grid' | 'list';
    selectionMode?: boolean;
    selectedIds?: Set<number>;
    onToggleSelect?: (id: number) => void;
  }

  let { books, mode = 'grid', selectionMode = false, selectedIds = new Set(), onToggleSelect }: Props = $props();

  function formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
  }
</script>

{#if books.length === 0}
  <div class="flex flex-col items-center justify-center gap-3 py-16 text-muted-foreground">
    <BookOpen class="h-12 w-12" />
    <p>No books found</p>
  </div>
{:else if mode === 'list'}
  <div class="divide-y rounded-lg border bg-card overflow-hidden">
    {#each books as book (book.id)}
      {@const cover = bookCoverUrl(book)}
      {@const author = book.authors?.[0]?.name ?? null}
      {@const series = book.series?.[0]?.name ?? null}
      {@const fmt = book.files?.[0]?.format ?? null}
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <a
        href="/book/{book.id}"
        class={cn("group flex items-center gap-4 px-4 py-2.5 transition-colors hover:bg-muted/40", selectionMode && selectedIds.has(book.id) && "bg-primary/10")}
        onclick={(e) => { if (selectionMode) { e.preventDefault(); onToggleSelect?.(book.id); } }}
      >
        {#if selectionMode}
          <button
            class={cn(
              "flex h-5 w-5 shrink-0 items-center justify-center rounded border-2 transition-colors",
              selectedIds.has(book.id) ? "border-primary bg-primary text-primary-foreground" : "border-muted-foreground/30"
            )}
            onclick={(e) => { e.stopPropagation(); onToggleSelect?.(book.id); }}
          >
            {#if selectedIds.has(book.id)}<Check class="h-3 w-3" />{/if}
          </button>
        {/if}
        <!-- Thumbnail -->
        <div class="h-12 w-8 shrink-0 overflow-hidden rounded bg-muted">
          {#if cover}
            <img src={cover} alt={book.title} class="h-full w-full object-cover" loading="lazy" />
          {:else}
            <div class="flex h-full w-full items-center justify-center">
              <BookOpen class="h-3.5 w-3.5 text-muted-foreground/30" />
            </div>
          {/if}
        </div>

        <!-- Title + author + series -->
        <div class="min-w-0 flex-1">
          <p class="font-serif text-sm font-medium leading-snug text-foreground line-clamp-1 group-hover:text-foreground/80">
            {book.title}
          </p>
          <p class="mt-0.5 text-xs text-muted-foreground truncate">
            {#if author}{author}{/if}{#if author && series} · {/if}{#if series}<span class="text-amber-600/80 dark:text-amber-400/70">{series}</span>{/if}
          </p>
        </div>

        <!-- Format + date -->
        <div class="flex shrink-0 items-center gap-3">
          {#if fmt}
            <span class="hidden text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/50 sm:block">
              {fmt}
            </span>
          {/if}
          {#if book.abs_item_id}
            <Headphones class="hidden h-3.5 w-3.5 text-muted-foreground/40 sm:block" title="Audiobook available" />
          {/if}
          <span class="hidden text-[11px] tabular-nums text-muted-foreground/40 md:block">
            {formatDate(book.created_at)}
          </span>
        </div>
      </a>
    {/each}
  </div>
{:else}
  <div class="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
    {#each books as book (book.id)}
      <BookCard {book} {selectionMode} selected={selectedIds.has(book.id)} {onToggleSelect} />
    {/each}
  </div>
{/if}
