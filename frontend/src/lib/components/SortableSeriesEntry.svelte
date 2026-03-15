<script lang="ts">
  import { BookOpen, GripVertical, X } from 'lucide-svelte';
  import { useSortable } from '@dnd-kit-svelte/svelte/sortable';
  import { bookCoverUrl } from '$lib/api/client';
  import type { SeriesEntry } from '$lib/types/index';

  interface Props {
    entry: SeriesEntry & { _key: number };
    index: number;
    onRemove: () => void;
  }

  let { entry, index, onRemove }: Props = $props();

  const { ref, handleRef, isDragging } = useSortable({
    id: () => entry._key,
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
  <!-- Drag handle -->
  <button
    {@attach handleRef}
    class="shrink-0 cursor-grab active:cursor-grabbing text-muted-foreground/30 hover:text-muted-foreground/60 touch-none transition-colors"
    onclick={(e) => e.preventDefault()}
    aria-label="Drag to reorder"
  >
    <GripVertical class="h-4 w-4" />
  </button>

  <!-- Cover -->
  <div class="h-10 w-7 shrink-0 overflow-hidden rounded shadow-sm">
    {#if cover}
      <img src={cover} alt="" class="h-full w-full object-cover" loading="lazy" />
    {:else}
      <div class="flex h-full w-full items-center justify-center bg-muted">
        <BookOpen class="h-3 w-3 text-muted-foreground/30" />
      </div>
    {/if}
  </div>

  <!-- Title + author -->
  <div class="min-w-0 flex-1">
    <p class="truncate text-sm font-medium">{entry.book.title}</p>
    {#if author}
      <p class="truncate text-xs text-muted-foreground">{author}</p>
    {/if}
  </div>

  <!-- Editable metadata -->
  <div class="flex shrink-0 items-center gap-1.5">
    <input
      type="number"
      bind:value={entry.position}
      placeholder="#"
      step="0.5"
      class="w-14 rounded border bg-background px-1.5 py-0.5 text-center text-xs tabular-nums focus:outline-none focus:ring-1 focus:ring-ring"
      title="Position"
    />
    <input
      type="text"
      bind:value={entry.volume}
      placeholder="Vol."
      class="w-16 rounded border bg-background px-1.5 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
      title="Volume"
    />
    <input
      type="text"
      bind:value={entry.arc}
      placeholder="Arc"
      class="w-20 rounded border bg-background px-1.5 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
      title="Arc / Story Arc"
    />
  </div>

  <!-- Remove -->
  <button
    onclick={onRemove}
    class="shrink-0 text-muted-foreground/30 hover:text-destructive transition-colors"
    title="Remove from series"
  >
    <X class="h-3.5 w-3.5" />
  </button>
</div>
