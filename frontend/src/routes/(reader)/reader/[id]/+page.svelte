<script lang="ts">
  import { goto } from '$app/navigation';
  import EpubReader from '$lib/components/EpubReader.svelte';
  import PdfReader from '$lib/components/PdfReader.svelte';
  import ComicReader from '$lib/components/ComicReader.svelte';
  import ReaderNotesPanel from '$lib/components/ReaderNotesPanel.svelte';
  import { saveReadProgress } from '$lib/api/client';
  import { MessageSquarePlus } from 'lucide-svelte';
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();
  let book = data.book;

  // Pick the first readable file, preferring formats we can render
  const FORMAT_PRIORITY = ['epub', 'cbz', 'pdf', 'cbr'];
  let file = $derived(
    book?.files?.slice().sort((a, b) => {
      const ai = FORMAT_PRIORITY.indexOf(a.format.toLowerCase());
      const bi = FORMAT_PRIORITY.indexOf(b.format.toLowerCase());
      return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
    })[0] ?? null
  );

  let format = $derived(file?.format?.toLowerCase() ?? '');

  let notesOpen = $state(false);
  let currentLocation = $state<string | undefined>(undefined);

  function handleClose() {
    goto(`/book/${book?.id}`);
  }

  async function handleProgress(page: number, total: number, pct: number) {
    if (!book || !file) return;
    try {
      await saveReadProgress(book.id, {
        current_page: page + 1,
        total_pages: total,
        percentage: pct,
        file_id: file.id,
        format: file.format,
      });
    } catch {
      // non-critical
    }
  }

  function handleLocationChange(location: string) {
    currentLocation = location;
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
        <EpubReader
          bookId={book.id}
          fileId={file.id}
          onClose={handleClose}
          onLocationChange={handleLocationChange}
        />
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
