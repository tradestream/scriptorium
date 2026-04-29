<script lang="ts">
  import { BookOpen, GripVertical, X } from 'lucide-svelte';
  import { useSortable } from '@dnd-kit-svelte/svelte/sortable';
  import { bookCoverUrl } from '$lib/api/client';
  import type { ReadingListEntry } from '$lib/types/index';

  interface Props {
    entry: ReadingListEntry;
    index: number;
    onRemove: () => void;
  }

  let { entry, index, onRemove }: Props = $props();

  const { ref, handleRef, isDragging } = useSortable({
    id: () => entry.id,
    index: () => index,
    feedback: 'move',
  });

  let cover = $derived(bookCoverUrl(entry.book) ?? '');
  let author = $derived(entry.book.authors?.[0]?.name ?? '');
</script>

<div
  {@attach ref}
  class="group flex items-center gap-3 rounded-lg border bg-card px-3 py-2 transition-shadow {isDragging.current ? 'opacity-40 shadow-lg' : ''}"
>
  <button
    {@attach handleRef}
    class="shrink-0 cursor-grab active:cursor-grabbing text-muted-foreground/30 hover:text-muted-foreground/60 touch-none transition-colors"
    onclick={(e) => e.preventDefault()}
    aria-label="Drag to reorder"
  >
    <GripVertical class="h-4 w-4" />
  </button>

  <span class="w-6 shrink-0 text-center text-xs font-mono tabular-nums text-muted-foreground/50">
    {index + 1}
  </span>

  <div class="h-10 w-7 shrink-0 overflow-hidden rounded shadow-sm">
    {#if cover}
      <img src={cover} alt="" class="h-full w-full object-cover" loading="lazy" />
    {:else}
      <div class="flex h-full w-full items-center justify-center bg-muted">
        <BookOpen class="h-3 w-3 text-muted-foreground/30" />
      </div>
    {/if}
  </div>

  <a href="/book/{entry.book.id}" class="min-w-0 flex-1">
    <p class="truncate text-sm font-medium hover:text-primary transition-colors">{entry.book.title}</p>
    {#if author}
      <p class="truncate text-xs text-muted-foreground">{author}</p>
    {/if}
  </a>

  <button
    onclick={onRemove}
    class="shrink-0 text-muted-foreground/30 hover:text-destructive transition-colors"
    title="Remove from list"
    aria-label="Remove"
  >
    <X class="h-3.5 w-3.5" />
  </button>
</div>
