<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { Button } from "$lib/components/ui/button";
  import { ChevronLeft, ChevronRight, Settings, X } from "lucide-svelte";
  import { downloadBookFile } from "$lib/api/client";

  interface Props {
    bookId: number;
    fileId: number;
    initialPage?: number;
    onProgress?: (page: number, total: number, pct: number) => void;
    onLocationChange?: (location: string) => void;
    onClose?: () => void;
  }

  let { bookId, fileId, initialPage = 0, onProgress, onLocationChange, onClose }: Props = $props();

  let container = $state<HTMLElement | null>(null);
  let rendition: any = $state(null);
  let book: any = $state(null);
  let currentPage = $state(0);
  let totalPages = $state(0);
  let loading = $state(true);
  let error = $state('');
  let fontSize = $state(100); // percentage
  let showSettings = $state(false);

  onMount(async () => {
    if (!container) return;
    try {
      // Download blob so we can pass it without auth headers
      const blob = await downloadBookFile(bookId, fileId);
      const blobUrl = URL.createObjectURL(blob);

      const { default: Epub } = await import('epubjs');
      book = Epub(blobUrl);
      rendition = book.renderTo(container, {
        width: '100%',
        height: '100%',
        spread: 'auto',
        flow: 'paginated',
      });

      await book.ready;
      await book.locations.generate(1024);
      totalPages = book.locations.total;

      rendition.on('relocated', (location: any) => {
        const pg = book.locations.locationFromCfi(location.start.cfi);
        currentPage = typeof pg === 'number' ? pg : 0;
        const pct = totalPages > 0 ? (currentPage / totalPages) * 100 : 0;
        onProgress?.(currentPage, totalPages, pct);
        if (location.start?.cfi) onLocationChange?.(location.start.cfi);
      });

      if (initialPage > 0 && book.locations.cfiFromLocation) {
        const cfi = book.locations.cfiFromLocation(initialPage);
        await rendition.display(cfi);
      } else {
        await rendition.display();
      }

      loading = false;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load book';
      loading = false;
    }
  });

  onDestroy(() => {
    rendition?.destroy();
    book?.destroy();
  });

  function prevPage() { rendition?.prev(); }
  function nextPage() { rendition?.next(); }

  function applyFontSize() {
    rendition?.themes.fontSize(`${fontSize}%`);
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') nextPage();
    if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') prevPage();
    if (e.key === 'Escape') onClose?.();
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="relative flex h-full flex-col bg-background">
  <!-- Toolbar -->
  <div class="flex items-center justify-between border-b bg-background/95 px-4 py-2 backdrop-blur">
    <Button variant="ghost" size="icon" onclick={onClose}>
      <X class="h-4 w-4" />
    </Button>
    <div class="flex items-center gap-2 text-sm text-muted-foreground">
      {#if totalPages > 0}
        <span>{currentPage} / {totalPages}</span>
      {/if}
    </div>
    <Button variant="ghost" size="icon" onclick={() => showSettings = !showSettings}>
      <Settings class="h-4 w-4" />
    </Button>
  </div>

  <!-- Settings panel -->
  {#if showSettings}
    <div class="border-b bg-muted/50 px-4 py-3">
      <div class="flex items-center gap-3">
        <label class="text-sm font-medium" for="font-size">Font size: {fontSize}%</label>
        <input
          id="font-size"
          type="range"
          min="70"
          max="200"
          step="10"
          bind:value={fontSize}
          onchange={applyFontSize}
          class="flex-1"
        />
      </div>
    </div>
  {/if}

  <!-- Reader area -->
  <div class="relative flex-1 overflow-hidden">
    {#if loading}
      <div class="flex h-full items-center justify-center">
        <div class="text-center">
          <div class="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent"></div>
          <p class="mt-3 text-sm text-muted-foreground">Loading book...</p>
        </div>
      </div>
    {:else if error}
      <div class="flex h-full items-center justify-center">
        <p class="text-destructive">{error}</p>
      </div>
    {:else}
      <!-- Navigation zones -->
      <button
        class="absolute left-0 top-0 z-10 h-full w-16 cursor-pointer opacity-0 hover:opacity-100 flex items-center justify-start pl-2"
        onclick={prevPage}
        aria-label="Previous page"
      >
        <ChevronLeft class="h-8 w-8 text-muted-foreground/70" />
      </button>
      <button
        class="absolute right-0 top-0 z-10 h-full w-16 cursor-pointer opacity-0 hover:opacity-100 flex items-center justify-end pr-2"
        onclick={nextPage}
        aria-label="Next page"
      >
        <ChevronRight class="h-8 w-8 text-muted-foreground/70" />
      </button>
    {/if}

    <!-- epub.js mounts here -->
    <div bind:this={container} class="h-full w-full"></div>
  </div>
</div>
