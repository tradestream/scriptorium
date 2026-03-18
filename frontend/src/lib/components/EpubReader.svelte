<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { Button } from "$lib/components/ui/button";
  import { ChevronLeft, ChevronRight, Settings, X, Minus, Plus, AlignJustify, Columns2, Moon, Sun } from "lucide-svelte";
  import { downloadBookFile } from "$lib/api/client";

  interface Props {
    bookId: number;
    fileId: number;
    initialCfi?: string;
    initialPage?: number;
    onProgress?: (page: number, total: number, pct: number) => void;
    onLocationChange?: (location: string) => void;
    onClose?: () => void;
  }

  let { bookId, fileId, initialCfi = '', initialPage = 0, onProgress, onLocationChange, onClose }: Props = $props();

  let container = $state<HTMLElement | null>(null);
  let rendition: any = $state(null);
  let book: any = $state(null);
  let currentPage = $state(0);
  let totalPages = $state(0);
  let loading = $state(true);
  let error = $state('');
  let showSettings = $state(false);
  let chapterTitle = $state('');

  // Reader settings (BookLore-inspired)
  let fontSize = $state(100);
  let lineHeight = $state(1.5);
  let justify = $state(true);
  let columns = $state(1);
  let darkMode = $state(typeof window !== 'undefined' && document.documentElement.classList.contains('dark'));
  let flow = $state<'paginated' | 'scrolled'>('paginated');

  // Touch/swipe state
  let touchStartX = 0;
  let touchStartY = 0;
  const SWIPE_THRESHOLD = 50;

  onMount(async () => {
    if (!container) return;
    try {
      const blob = await downloadBookFile(bookId, fileId);
      const arrayBuffer = await blob.arrayBuffer();

      const { default: Epub } = await import('epubjs');
      book = Epub();
      await book.open(arrayBuffer, "binary");

      rendition = book.renderTo(container, {
        width: '100%',
        height: '100%',
        spread: columns > 1 ? 'auto' : 'none',
        flow: flow,
        minSpreadWidth: columns > 1 ? 800 : 99999,
        allowScriptedContent: false,
      });

      // Apply initial styles
      applyStyles();

      await book.ready;
      await book.locations.generate(1024);
      totalPages = book.locations.total;

      rendition.on('relocated', (location: any) => {
        const pg = book.locations.locationFromCfi(location.start.cfi);
        currentPage = typeof pg === 'number' ? pg : 0;
        const pct = totalPages > 0 ? (currentPage / totalPages) * 100 : 0;
        onProgress?.(currentPage, totalPages, pct);
        if (location.start?.cfi) onLocationChange?.(location.start.cfi);

        // Update chapter title
        try {
          const section = book.spine.get(location.start.href);
          if (section) {
            const navItem = book.navigation?.toc?.find((t: any) => t.href?.includes(section.href));
            chapterTitle = navItem?.label?.trim() || '';
          }
        } catch { /* non-critical */ }
      });

      // Restore position
      if (initialCfi) {
        await rendition.display(initialCfi);
      } else if (initialPage > 0 && book.locations.cfiFromLocation) {
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

  function applyStyles() {
    if (!rendition) return;
    rendition.themes.default({
      'body': {
        'font-size': `${fontSize}% !important`,
        'line-height': `${lineHeight} !important`,
        'text-align': justify ? 'justify' : 'start',
        '-webkit-hyphens': justify ? 'auto' : 'none',
        'hyphens': justify ? 'auto' : 'none',
      },
      'p': {
        'line-height': `${lineHeight} !important`,
      },
    });

    if (darkMode) {
      rendition.themes.override('color', '#e0e0e0');
      rendition.themes.override('background', '#1a1a1a');
    } else {
      rendition.themes.override('color', '#1a1a1a');
      rendition.themes.override('background', '#fafaf9');
    }
  }

  function changeFontSize(delta: number) {
    fontSize = Math.max(70, Math.min(200, fontSize + delta));
    applyStyles();
  }

  function changeLineHeight(delta: number) {
    lineHeight = Math.max(1.0, Math.min(3.0, +(lineHeight + delta).toFixed(1)));
    applyStyles();
  }

  function toggleJustify() {
    justify = !justify;
    applyStyles();
  }

  function toggleDarkMode() {
    darkMode = !darkMode;
    applyStyles();
  }

  function toggleColumns() {
    columns = columns === 1 ? 2 : 1;
    if (rendition) {
      rendition.spread(columns > 1 ? 'auto' : 'none');
    }
  }

  function toggleFlow() {
    flow = flow === 'paginated' ? 'scrolled' : 'paginated';
    if (rendition) {
      rendition.flow(flow);
    }
  }

  // Touch/swipe handlers
  function handleTouchStart(e: TouchEvent) {
    touchStartX = e.touches[0].clientX;
    touchStartY = e.touches[0].clientY;
  }

  function handleTouchEnd(e: TouchEvent) {
    const deltaX = e.changedTouches[0].clientX - touchStartX;
    const deltaY = e.changedTouches[0].clientY - touchStartY;
    // Only trigger if horizontal swipe is dominant
    if (Math.abs(deltaX) > SWIPE_THRESHOLD && Math.abs(deltaX) > Math.abs(deltaY)) {
      if (deltaX < 0) nextPage();
      else prevPage();
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown' || e.key === ' ') { e.preventDefault(); nextPage(); }
    if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') { e.preventDefault(); prevPage(); }
    if (e.key === 'Escape') onClose?.();
  }

  const pct = $derived(totalPages > 0 ? Math.round((currentPage / totalPages) * 100) : 0);
</script>

<svelte:window onkeydown={handleKeydown} />

<div
  class="relative flex h-full flex-col {darkMode ? 'bg-[#1a1a1a] text-[#e0e0e0]' : 'bg-[#fafaf9] text-[#1a1a1a]'}"
  ontouchstart={handleTouchStart}
  ontouchend={handleTouchEnd}
>
  <!-- Toolbar -->
  <div class="flex items-center justify-between border-b px-4 py-2 {darkMode ? 'border-white/10 bg-[#1a1a1a]/95' : 'border-black/10 bg-[#fafaf9]/95'} backdrop-blur">
    <Button variant="ghost" size="icon" onclick={onClose} class={darkMode ? 'text-white/70 hover:text-white' : ''}>
      <X class="h-4 w-4" />
    </Button>
    <div class="flex flex-col items-center gap-0 min-w-0 flex-1 mx-4">
      {#if chapterTitle}
        <span class="text-xs truncate max-w-48 {darkMode ? 'text-white/50' : 'text-black/50'}">{chapterTitle}</span>
      {/if}
      {#if totalPages > 0}
        <span class="text-xs tabular-nums {darkMode ? 'text-white/40' : 'text-black/40'}">{pct}%</span>
      {/if}
    </div>
    <Button variant="ghost" size="icon" onclick={() => showSettings = !showSettings} class={darkMode ? 'text-white/70 hover:text-white' : ''}>
      <Settings class="h-4 w-4" />
    </Button>
  </div>

  <!-- Settings panel -->
  {#if showSettings}
    <div class="border-b px-4 py-3 space-y-3 {darkMode ? 'border-white/10 bg-[#222]' : 'border-black/10 bg-white'}">
      <!-- Font size -->
      <div class="flex items-center justify-between">
        <span class="text-xs font-medium {darkMode ? 'text-white/60' : 'text-black/60'}">Font size</span>
        <div class="flex items-center gap-2">
          <button onclick={() => changeFontSize(-10)} class="rounded-md border px-2 py-1 text-xs {darkMode ? 'border-white/20 hover:bg-white/10' : 'border-black/20 hover:bg-black/5'}">
            <Minus class="h-3 w-3" />
          </button>
          <span class="text-xs tabular-nums w-10 text-center">{fontSize}%</span>
          <button onclick={() => changeFontSize(10)} class="rounded-md border px-2 py-1 text-xs {darkMode ? 'border-white/20 hover:bg-white/10' : 'border-black/20 hover:bg-black/5'}">
            <Plus class="h-3 w-3" />
          </button>
        </div>
      </div>
      <!-- Line height -->
      <div class="flex items-center justify-between">
        <span class="text-xs font-medium {darkMode ? 'text-white/60' : 'text-black/60'}">Line height</span>
        <div class="flex items-center gap-2">
          <button onclick={() => changeLineHeight(-0.1)} class="rounded-md border px-2 py-1 text-xs {darkMode ? 'border-white/20 hover:bg-white/10' : 'border-black/20 hover:bg-black/5'}">
            <Minus class="h-3 w-3" />
          </button>
          <span class="text-xs tabular-nums w-10 text-center">{lineHeight}</span>
          <button onclick={() => changeLineHeight(0.1)} class="rounded-md border px-2 py-1 text-xs {darkMode ? 'border-white/20 hover:bg-white/10' : 'border-black/20 hover:bg-black/5'}">
            <Plus class="h-3 w-3" />
          </button>
        </div>
      </div>
      <!-- Toggles row -->
      <div class="flex items-center gap-2">
        <button
          onclick={toggleJustify}
          class="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs {justify ? (darkMode ? 'border-white/30 bg-white/10' : 'border-black/30 bg-black/5') : (darkMode ? 'border-white/10' : 'border-black/10')}"
          title="Toggle justify"
        >
          <AlignJustify class="h-3 w-3" />
          Justify
        </button>
        <button
          onclick={toggleColumns}
          class="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs {columns > 1 ? (darkMode ? 'border-white/30 bg-white/10' : 'border-black/30 bg-black/5') : (darkMode ? 'border-white/10' : 'border-black/10')}"
          title="Toggle two-page spread"
        >
          <Columns2 class="h-3 w-3" />
          {columns > 1 ? '2-up' : '1-up'}
        </button>
        <button
          onclick={toggleFlow}
          class="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs {darkMode ? 'border-white/10' : 'border-black/10'}"
          title="Toggle scroll mode"
        >
          {flow === 'paginated' ? 'Paged' : 'Scroll'}
        </button>
        <button
          onclick={toggleDarkMode}
          class="ml-auto flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs {darkMode ? 'border-white/10' : 'border-black/10'}"
          title="Toggle dark mode"
        >
          {#if darkMode}<Sun class="h-3 w-3" />{:else}<Moon class="h-3 w-3" />{/if}
        </button>
      </div>
    </div>
  {/if}

  <!-- Reader area -->
  <div class="relative flex-1 overflow-hidden">
    {#if loading}
      <div class="flex h-full items-center justify-center">
        <div class="text-center">
          <div class="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-current border-t-transparent opacity-40"></div>
          <p class="mt-3 text-sm opacity-50">Loading book...</p>
        </div>
      </div>
    {:else if error}
      <div class="flex h-full items-center justify-center">
        <p class="text-destructive">{error}</p>
      </div>
    {:else}
      <!-- Click navigation zones (desktop) -->
      <button
        class="absolute left-0 top-0 z-10 h-full w-[15%] cursor-pointer opacity-0 hover:opacity-100 flex items-center justify-start pl-2"
        onclick={prevPage}
        aria-label="Previous page"
      >
        <ChevronLeft class="h-8 w-8 opacity-30" />
      </button>
      <button
        class="absolute right-0 top-0 z-10 h-full w-[15%] cursor-pointer opacity-0 hover:opacity-100 flex items-center justify-end pr-2"
        onclick={nextPage}
        aria-label="Next page"
      >
        <ChevronRight class="h-8 w-8 opacity-30" />
      </button>
    {/if}

    <!-- epub.js mounts here — constrained to ~680px like Medium for comfortable reading -->
    <div bind:this={container} class="h-full w-full mx-auto" style="max-width: 720px; padding: 0 2rem;"></div>
  </div>

  <!-- Progress bar at bottom -->
  {#if totalPages > 0 && !loading}
    <div class="h-0.5 w-full {darkMode ? 'bg-white/5' : 'bg-black/5'}">
      <div
        class="h-full transition-all {darkMode ? 'bg-white/20' : 'bg-black/15'}"
        style="width: {pct}%"
      ></div>
    </div>
  {/if}
</div>
