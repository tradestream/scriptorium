<script lang="ts">
  import { onMount } from "svelte";
  import { Button } from "$lib/components/ui/button";
  import { ChevronLeft, ChevronRight, X, Maximize2, Minimize2 } from "lucide-svelte";
  import { getComicPageCount, comicPageUrl, getAuthToken } from "$lib/api/client";

  interface Props {
    bookId: number;
    fileId: number;
    initialPage?: number;
    onProgress?: (page: number, total: number, pct: number) => void;
    onLocationChange?: (location: string) => void;
    onClose?: () => void;
  }

  let { bookId, fileId, initialPage = 0, onProgress, onLocationChange, onClose }: Props = $props();

  let totalPages = $state(0);
  let currentPage = $state(initialPage);
  let loading = $state(true);
  let imageLoading = $state(false);
  let error = $state('');
  let fitMode = $state<'width' | 'height'>('height');
  let doublePage = $state(false);

  // Build an authenticated page URL
  function pageUrl(page: number): string {
    const base = comicPageUrl(bookId, fileId, page);
    const token = getAuthToken();
    return token ? `${base}?token=${encodeURIComponent(token)}` : base;
  }

  onMount(async () => {
    try {
      const info = await getComicPageCount(bookId, fileId);
      totalPages = info.count;
      loading = false;
      reportProgress();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load comic';
      loading = false;
    }
  });

  function reportProgress() {
    // Single-page comics divide by zero in the naive ``currentPage / (total - 1)``;
    // the resulting ``NaN`` becomes ``null`` in ``JSON.stringify`` and the
    // backend silently drops the save. A one-page comic on its only page
    // is by definition 100% read.
    const pct =
      totalPages <= 1 ? (totalPages === 1 ? 100 : 0) : (currentPage / (totalPages - 1)) * 100;
    onProgress?.(currentPage, totalPages, pct);
    onLocationChange?.(`page:${currentPage + 1}`);
  }

  function prevPage() {
    if (currentPage > 0) {
      currentPage = doublePage ? Math.max(0, currentPage - 2) : currentPage - 1;
      reportProgress();
    }
  }

  function nextPage() {
    const step = doublePage ? 2 : 1;
    if (currentPage + step - 1 < totalPages) {
      currentPage = Math.min(totalPages - 1, currentPage + step);
      reportProgress();
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown' || e.key === ' ') nextPage();
    if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') prevPage();
    if (e.key === 'Escape') onClose?.();
    if (e.key === 'd') doublePage = !doublePage;
    if (e.key === 'f') fitMode = fitMode === 'height' ? 'width' : 'height';
  }

  function handleClick(e: MouseEvent) {
    const target = e.currentTarget as HTMLElement;
    const x = e.clientX / target.clientWidth;
    if (x < 0.33) prevPage();
    else if (x > 0.67) nextPage();
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="flex h-full flex-col bg-black">
  <!-- Toolbar -->
  <div class="flex items-center justify-between bg-black/80 px-4 py-2 backdrop-blur">
    <Button variant="ghost" size="icon" class="text-white hover:text-white hover:bg-white/20" onclick={onClose}>
      <X class="h-4 w-4" />
    </Button>

    <div class="flex items-center gap-3">
      <Button variant="ghost" size="icon" class="text-white hover:text-white hover:bg-white/20" onclick={prevPage} disabled={currentPage <= 0}>
        <ChevronLeft class="h-4 w-4" />
      </Button>
      <span class="text-sm text-white/80">
        {currentPage + 1}{doublePage && currentPage + 1 < totalPages ? `–${currentPage + 2}` : ''} / {totalPages}
      </span>
      <Button variant="ghost" size="icon" class="text-white hover:text-white hover:bg-white/20" onclick={nextPage} disabled={currentPage >= totalPages - 1}>
        <ChevronRight class="h-4 w-4" />
      </Button>
    </div>

    <div class="flex gap-1">
      <button
        class="rounded px-2 py-1 text-xs text-white/70 hover:bg-white/20 hover:text-white {doublePage ? 'bg-white/20' : ''}"
        onclick={() => doublePage = !doublePage}
        title="Toggle double-page spread (D)"
      >2P</button>
      <button
        class="rounded px-2 py-1 text-xs text-white/70 hover:bg-white/20 hover:text-white"
        onclick={() => fitMode = fitMode === 'height' ? 'width' : 'height'}
        title="Toggle fit mode (F)"
      >
        {fitMode === 'height' ? 'Fit H' : 'Fit W'}
      </button>
    </div>
  </div>

  <!-- Page display -->
  <div
    class="flex flex-1 cursor-pointer items-center justify-center overflow-hidden"
    onclick={handleClick}
    role="presentation"
  >
    {#if loading}
      <div class="text-center text-white">
        <div class="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-white border-t-transparent"></div>
        <p class="mt-3 text-sm opacity-70">Loading comic...</p>
      </div>
    {:else if error}
      <p class="text-red-400">{error}</p>
    {:else}
      <div class="flex gap-1">
        {#if doublePage && currentPage > 0}
          <img
            src={pageUrl(currentPage - 1)}
            alt="Page {currentPage}"
            class="{fitMode === 'height' ? 'max-h-full' : 'max-w-1/2'} object-contain select-none"
            draggable="false"
          />
        {/if}
        <img
          src={pageUrl(currentPage)}
          alt="Page {currentPage + 1}"
          class="{fitMode === 'height' ? 'max-h-full' : 'max-w-full'} object-contain select-none"
          draggable="false"
        />
      </div>
    {/if}
  </div>
</div>
