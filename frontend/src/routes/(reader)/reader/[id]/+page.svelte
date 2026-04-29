<script lang="ts">
  import { goto } from '$app/navigation';
  import { onDestroy, onMount } from 'svelte';
  import EpubReader from '$lib/components/EpubReader.svelte';
  import PdfReader from '$lib/components/PdfReader.svelte';
  import ComicReader from '$lib/components/ComicReader.svelte';
  import ReaderNotesPanel from '$lib/components/ReaderNotesPanel.svelte';
  import { ReaderProgress } from '$lib/reader/progress.svelte';
  import { MessageSquarePlus } from 'lucide-svelte';
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();
  let book = $derived(data.book);

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

  // ReaderProgress encapsulates load/save/session-timer/furthest-watermark
  // logic. Built lazily because we need book + file resolved first.
  let progress = $state<ReaderProgress | null>(null);
  // Bumped to remount the reader when we jump to the furthest cursor.
  let readerKey = $state(0);

  // Fixed-layout readers (PDF, CBZ/CBR) use ``page:N`` in the cursor field
  // instead of an opaque CFI. Parse that into a 1-based page index so we
  // can hand it to PdfReader (1-based) and ComicReader (0-based after -1).
  let savedPage = $derived.by((): number => {
    const loc = progress?.initialCfi;
    if (!loc) return 0;
    const m = loc.match(/^page:(\d+)/);
    return m ? parseInt(m[1], 10) : 0;
  });

  onMount(async () => {
    if (!book || !file) return;
    progress = new ReaderProgress({
      bookId: book.id,
      fileId: file.id,
      format: file.format,
    });
    await progress.init();
  });

  onDestroy(() => {
    // Fire-and-forget — onDestroy can't await, but flush() is safe to drop.
    void progress?.dispose();
  });

  function handleClose() {
    goto(`/book/${book?.id}`);
  }

  function handleProgress(page: number, total: number, pct: number) {
    progress?.reportProgress(page, total, pct);
  }

  function handleLocationChange(location: string) {
    progress?.setLocation(location);
  }

  function jumpToFurthest() {
    if (progress?.jumpToFurthest()) readerKey += 1;
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
      {#if format === 'epub' || format === 'pdf' || format === 'cbz' || format === 'cbr'}
        {#if progress?.loaded}
          <!-- Wrap every format in {#key readerKey} so ``Jump to furthest``
               remounts the active reader with the new initial position
               regardless of EPUB / PDF / comic. -->
          {#key readerKey}
            {#if format === 'epub'}
              <EpubReader
                bookId={book.id}
                fileId={file.id}
                initialCfi={progress.initialCfi}
                onClose={handleClose}
                onProgress={handleProgress}
                onLocationChange={handleLocationChange}
              />
            {:else if format === 'pdf'}
              <PdfReader
                bookId={book.id}
                fileId={file.id}
                initialPage={savedPage || 1}
                onClose={handleClose}
                onProgress={handleProgress}
                onLocationChange={handleLocationChange}
              />
            {:else}
              <ComicReader
                bookId={book.id}
                fileId={file.id}
                initialPage={savedPage > 0 ? savedPage - 1 : 0}
                onClose={handleClose}
                onProgress={handleProgress}
                onLocationChange={handleLocationChange}
              />
            {/if}
          {/key}
        {:else}
          <div class="flex h-full items-center justify-center bg-black text-white/60 text-sm">
            Loading…
          </div>
        {/if}

        <!-- Furthest-jump prompt is format-agnostic — the saved location
             is restored via initialCfi (epub) or initialPage (fixed-layout)
             on the next mount triggered by ``readerKey``. -->
        {#if progress?.showFurthestPrompt}
          <div class="absolute left-1/2 top-4 z-30 -translate-x-1/2">
            <div class="flex items-center gap-3 rounded-full border bg-background/95 px-4 py-2 text-sm shadow-lg backdrop-blur">
              <span class="font-medium">
                You read further on another device ({progress.furthestPct.toFixed(0)}% vs {progress.currentPct.toFixed(0)}%).
              </span>
              <button
                class="rounded-full bg-primary px-3 py-1 text-xs font-medium text-primary-foreground hover:opacity-90"
                onclick={jumpToFurthest}
              >
                Jump to furthest
              </button>
              <button
                class="rounded-full px-2 py-1 text-xs text-muted-foreground hover:bg-muted"
                onclick={() => progress?.dismissFurthestPrompt()}
                aria-label="Dismiss"
              >
                ✕
              </button>
            </div>
          </div>
        {/if}
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
          currentLocation={progress?.currentCfi}
          onClose={() => (notesOpen = false)}
        />
      </div>
    {/if}
  </div>
{/if}
