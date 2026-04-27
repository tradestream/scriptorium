<script lang="ts">
  import { goto } from '$app/navigation';
  import { onDestroy, onMount } from 'svelte';
  import EpubReader from '$lib/components/EpubReader.svelte';
  import PdfReader from '$lib/components/PdfReader.svelte';
  import ComicReader from '$lib/components/ComicReader.svelte';
  import ReaderNotesPanel from '$lib/components/ReaderNotesPanel.svelte';
  import { getBookProgress, saveReadProgress } from '$lib/api/client';
  import { MessageSquarePlus } from 'lucide-svelte';
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();
  let book = data.book;

  // Pick the first readable file, preferring formats we can render
  const FORMAT_PRIORITY = ['epub', 'cbz', 'pdf', 'cbr'];
  let file = $derived(
    book?.files?.slice().sort((a: { format: string }, b: { format: string }) => {
      const ai = FORMAT_PRIORITY.indexOf(a.format.toLowerCase());
      const bi = FORMAT_PRIORITY.indexOf(b.format.toLowerCase());
      return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
    })[0] ?? null
  );

  let format = $derived(file?.format?.toLowerCase() ?? '');

  let notesOpen = $state(false);
  let currentLocation = $state<string | undefined>(undefined);
  // Saved CFI from the previous reading session — passed to EpubReader so
  // the cursor is restored at the same paragraph instead of the chapter top.
  let initialCfi = $state<string>('');
  let progressLoaded = $state(false);

  // Sync-to-furthest prompt state. When the server reports a furthest_pct
  // meaningfully ahead of the current cursor (e.g. another device read
  // further into the book), we surface a one-tap "jump to furthest"
  // banner. Threshold is intentionally large to avoid noise from rounding.
  let furthestCfi = $state<string | undefined>(undefined);
  let furthestPct = $state<number>(0);
  let currentPct = $state<number>(0);
  let dismissedFurthestPrompt = $state(false);
  const FURTHEST_PROMPT_THRESHOLD_PCT = 2;

  // Session reading-time timer. We only count time spent with the tab visible
  // (visibilitychange suspends the count) so leaving a tab open doesn't
  // inflate ReadingState.total_time_seconds. The delta accumulates between
  // progress saves; each save reports & resets it.
  let lastTimerStart = Date.now();
  let pendingSeconds = 0;
  let isVisible = typeof document !== 'undefined' ? !document.hidden : true;

  function _flushTimer() {
    if (!isVisible) return;
    const now = Date.now();
    pendingSeconds += Math.max(0, Math.round((now - lastTimerStart) / 1000));
    lastTimerStart = now;
  }
  function _consumeDelta(): number {
    _flushTimer();
    const delta = pendingSeconds;
    pendingSeconds = 0;
    lastTimerStart = Date.now();
    return delta;
  }
  function _onVisibility() {
    if (typeof document === 'undefined') return;
    if (document.hidden) {
      _flushTimer();
      isVisible = false;
    } else {
      isVisible = true;
      lastTimerStart = Date.now();
    }
  }

  onMount(async () => {
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', _onVisibility);
    }
    lastTimerStart = Date.now();

    if (!book) {
      progressLoaded = true;
      return;
    }
    try {
      const saved = await getBookProgress(book.id);
      if (saved && (saved as any).cfi) {
        initialCfi = (saved as any).cfi;
      }
      if (saved) {
        currentPct = (saved as any).percentage ?? 0;
        furthestPct = (saved as any).furthest_percentage ?? 0;
        furthestCfi = (saved as any).furthest_cfi ?? undefined;
      }
    } catch {
      // non-critical
    }
    progressLoaded = true;
  });

  let showFurthestPrompt = $derived(
    !dismissedFurthestPrompt
    && furthestCfi
    && furthestCfi !== initialCfi
    && furthestPct - currentPct >= FURTHEST_PROMPT_THRESHOLD_PCT
  );

  onDestroy(() => {
    if (typeof document !== 'undefined') {
      document.removeEventListener('visibilitychange', _onVisibility);
    }
    // Final flush — any time accumulated since the last save is reported
    // with a no-position-change PUT so the session total is captured.
    if (book && file) {
      const delta = _consumeDelta();
      if (delta > 0) {
        const lastPct =
          typeof currentLocation === 'string' ? undefined : undefined;
        // Fire-and-forget; we don't await on unmount.
        void saveReadProgress(book.id, {
          percentage: lastPct ?? 0,
          file_id: file.id,
          format: file.format,
          cfi: currentLocation,
          time_spent_delta_seconds: delta,
        }).catch(() => {});
      }
    }
  });

  function handleClose() {
    goto(`/book/${book?.id}`);
  }

  async function handleProgress(page: number, total: number, pct: number) {
    if (!book || !file) return;
    const delta = _consumeDelta();
    try {
      await saveReadProgress(book.id, {
        current_page: page + 1,
        total_pages: total,
        percentage: pct,
        file_id: file.id,
        format: file.format,
        cfi: currentLocation,
        time_spent_delta_seconds: delta,
      });
    } catch {
      // non-critical
    }
  }

  function handleLocationChange(location: string) {
    currentLocation = location;
  }

  // Sync-to-furthest action: replace initialCfi with the furthest cursor
  // and bump readerKey so EpubReader remounts and displays from there.
  let readerKey = $state(0);
  function jumpToFurthest() {
    if (!furthestCfi) return;
    initialCfi = furthestCfi;
    currentPct = furthestPct;
    dismissedFurthestPrompt = true;
    readerKey += 1;
  }
  function dismissFurthestPrompt() {
    dismissedFurthestPrompt = true;
  }
</script>

{#if !book}
  <div class="flex h-screen items-center justify-center bg-black text-white">
    <p>Book not found</p>
  </div>
{:else if !file}
  <div class="flex h-screen flex-col items-center justify-center bg-black text-white gap-4">
    <p class="text-lg">No readable file available for this book.</p>
    <button
      class="rounded px-4 py-2 bg-white/20 hover:bg-white/30 text-sm"
      onclick={handleClose}
    >
      Go back
    </button>
  </div>
{:else}
  <div class="flex h-full overflow-hidden">
    <!-- Reader area -->
    <div class="relative flex-1 overflow-hidden">
      {#if format === 'epub'}
        {#if progressLoaded}
          {#key readerKey}
            <EpubReader
              bookId={book.id}
              fileId={file.id}
              initialCfi={initialCfi}
              onClose={handleClose}
              onProgress={handleProgress}
              onLocationChange={handleLocationChange}
            />
          {/key}
        {:else}
          <div class="flex h-full items-center justify-center bg-black text-white/60 text-sm">
            Loading…
          </div>
        {/if}

        {#if showFurthestPrompt}
          <div class="absolute left-1/2 top-4 z-30 -translate-x-1/2">
            <div class="flex items-center gap-3 rounded-full border bg-background/95 px-4 py-2 text-sm shadow-lg backdrop-blur">
              <span class="font-medium">
                You read further on another device ({furthestPct.toFixed(0)}% vs {currentPct.toFixed(0)}%).
              </span>
              <button
                class="rounded-full bg-primary px-3 py-1 text-xs font-medium text-primary-foreground hover:opacity-90"
                onclick={jumpToFurthest}
              >
                Jump to furthest
              </button>
              <button
                class="rounded-full px-2 py-1 text-xs text-muted-foreground hover:bg-muted"
                onclick={dismissFurthestPrompt}
                aria-label="Dismiss"
              >
                ✕
              </button>
            </div>
          </div>
        {/if}
      {:else if format === 'pdf'}
        <PdfReader
          bookId={book.id}
          fileId={file.id}
          onClose={handleClose}
          onProgress={handleProgress}
          onLocationChange={handleLocationChange}
        />
      {:else if format === 'cbz' || format === 'cbr'}
        <ComicReader
          bookId={book.id}
          fileId={file.id}
          onClose={handleClose}
          onProgress={handleProgress}
          onLocationChange={handleLocationChange}
        />
      {:else}
        <div class="flex h-full flex-col items-center justify-center bg-black text-white gap-4">
          <p class="text-lg">Unsupported format: <span class="uppercase font-bold">{format}</span></p>
          <button
            class="rounded px-4 py-2 bg-white/20 hover:bg-white/30 text-sm"
            onclick={handleClose}
          >
            Go back
          </button>
        </div>
      {/if}

      <!-- Floating notes toggle (shown when panel is closed) -->
      {#if !notesOpen}
        <button
          class="absolute right-4 top-14 z-20 flex items-center gap-1.5 rounded-full border bg-background/90 px-3 py-1.5 text-xs font-medium shadow backdrop-blur-sm hover:bg-background transition-colors"
          onclick={() => (notesOpen = true)}
          title="Open notes panel"
        >
          <MessageSquarePlus class="h-3.5 w-3.5 text-primary" />
          Notes
        </button>
      {/if}
    </div>

    <!-- Notes side panel -->
    {#if notesOpen}
      <div class="w-72 shrink-0 overflow-hidden border-l xl:w-80">
        <ReaderNotesPanel
          bookId={book.id}
          {currentLocation}
          onClose={() => (notesOpen = false)}
        />
      </div>
    {/if}
  </div>
{/if}
