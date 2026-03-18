<script lang="ts">
  import BookGrid from "$lib/components/BookGrid.svelte";
  import GroupedBooks from "$lib/components/GroupedBooks.svelte";
  import { Button } from "$lib/components/ui/button";
  import { Input } from "$lib/components/ui/input";
  import { LayoutGrid, List, Search, RefreshCw, ArrowUpDown, Layers, CheckSquare, X, ScanSearch, Sparkles, FileType, BookMarked } from "lucide-svelte";
  import * as api from "$lib/api/client";
  import type { Book } from "$lib/types/index";
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();
  let library = $derived(data.library);

  // ── View state ──────────────────────────────────────────────────────────────
  let viewMode = $state<'grid' | 'list'>('grid');
  let sortBy = $state<'date_added' | 'title'>('date_added');
  let searchInput = $state('');
  let search = $state('');           // debounced version
  let groupBy = $state<'series' | 'year' | 'publisher' | null>(null);
  let formatFilter = $state('');

  // ── Paginated book list (used when groupBy is null) ──────────────────────────
  const PAGE_SIZE = 60;
  let books = $state<Book[]>([]);
  let total = $state(0);
  let loading = $state(false);
  let loadingMore = $state(false);
  let skip = $state(0);
  let hasMore = $derived(books.length < total);

  // ── All books (used when groupBy is active) ──────────────────────────────────
  let allBooks = $state<Book[]>([]);
  let loadingAll = $state(false);

  async function loadAllBooks() {
    if (!library) return;
    loadingAll = true;
    try {
      const result = await api.getBooks({ library_id: library.id, limit: 5000, sort_by: 'title', format: formatFilter || undefined });
      allBooks = result.items;
    } catch (e) {
      console.error('Failed to load all books:', e);
    } finally {
      loadingAll = false;
    }
  }

  // ── Search debounce ──────────────────────────────────────────────────────────
  let debounceTimer: ReturnType<typeof setTimeout>;
  function onSearchInput(e: Event) {
    searchInput = (e.target as HTMLInputElement).value;
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => { search = searchInput; }, 300);
  }

  // ── Load books (paginated) ───────────────────────────────────────────────────
  async function loadBooks(reset = false) {
    if (!library || groupBy) return;
    if (reset) {
      loading = true;
      skip = 0;
    } else {
      loadingMore = true;
    }

    try {
      let result;
      if (search.trim()) {
        result = await api.searchBooks(search.trim(), {
          library_id: library.id,
          skip: reset ? 0 : skip,
          limit: PAGE_SIZE,
        });
      } else {
        result = await api.getBooks({
          library_id: library.id,
          skip: reset ? 0 : skip,
          limit: PAGE_SIZE,
          sort_by: sortBy,
          format: formatFilter || undefined,
        });
      }

      if (reset) {
        books = result.items;
      } else {
        books = [...books, ...result.items];
      }
      total = result.total;
      skip = (reset ? 0 : skip) + result.items.length;
    } catch (e) {
      console.error('Failed to load books:', e);
    } finally {
      loading = false;
      loadingMore = false;
    }
  }

  async function loadMore() {
    await loadBooks(false);
  }

  function infiniteScroll(node: HTMLElement) {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !loadingMore && hasMore) {
          loadMore();
        }
      },
      { rootMargin: '400px' }
    );
    observer.observe(node);
    return {
      destroy() {
        observer.disconnect();
      }
    };
  }

  async function scan() {
    if (!library) return;
    await api.scanLibrary(library.id);
  }

  // Reload paginated list when library, search, or sortBy changes (and not grouped)
  $effect(() => {
    void library;
    void search;
    void sortBy;
    void formatFilter;
    if (!groupBy) loadBooks(true);
  });

  // Load all books when groupBy is activated or format filter changes
  $effect(() => {
    void formatFilter;
    if (groupBy) loadAllBooks();
  });

  const GROUP_OPTIONS: { value: 'series' | 'year' | 'publisher'; label: string }[] = [
    { value: 'series', label: 'Series' },
    { value: 'year', label: 'Year' },
    { value: 'publisher', label: 'Publisher' },
  ];

  // ── Selection mode ─────────────────────────────────────────────────────────
  let selectionMode = $state(false);
  let selectedIds = $state(new Set<number>());
  let bulkActionRunning = $state(false);
  let bulkMsg = $state('');

  function toggleSelect(id: number) {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    selectedIds = next;
  }

  function selectAll() {
    const source = groupBy ? allBooks : books;
    selectedIds = new Set(source.map(b => b.id));
  }

  function deselectAll() {
    selectedIds = new Set();
  }

  function exitSelection() {
    selectionMode = false;
    selectedIds = new Set();
    bulkMsg = '';
  }

  async function bulkExtractIdentifiers() {
    if (selectedIds.size === 0) return;
    bulkActionRunning = true;
    bulkMsg = '';
    try {
      const r = await api.startBatchIdentifiers([...selectedIds]);
      bulkMsg = `Scanning ${r.total} books…`;
      // Poll for completion
      const poll = setInterval(async () => {
        try {
          const job = await api.getBulkIdentifiersJob(r.job_id);
          bulkMsg = `Scanning… ${job.done}/${job.total} (${job.found_isbn} ISBNs, ${job.found_doi} DOIs)`;
          if (job.status === 'done' || job.status === 'cancelled') {
            clearInterval(poll);
            bulkMsg = `Done — ${job.found_isbn} ISBNs, ${job.found_doi} DOIs found`;
            bulkActionRunning = false;
          }
        } catch {
          clearInterval(poll);
          bulkActionRunning = false;
        }
      }, 2000);
    } catch (e) {
      bulkMsg = e instanceof Error ? e.message : 'Failed';
      bulkActionRunning = false;
    }
  }

  async function bulkEnrich() {
    if (selectedIds.size === 0) return;
    bulkActionRunning = true;
    bulkMsg = `Enriching ${selectedIds.size} books…`;
    let done = 0;
    let failed = 0;
    for (const id of selectedIds) {
      try {
        await api.enrichBook(id);
        done++;
      } catch {
        failed++;
      }
      bulkMsg = `Enriching… ${done + failed}/${selectedIds.size}`;
    }
    bulkMsg = `Done — ${done} enriched, ${failed} failed`;
    bulkActionRunning = false;
  }

  // Bulk shelf assignment
  let showBulkShelfPicker = $state(false);
  let bulkShelves = $state<{ id: number; name: string }[]>([]);

  async function loadBulkShelves() {
    try {
      bulkShelves = await api.getShelves();
    } catch { /* ignore */ }
  }

  async function bulkAddToShelf(shelfId: number) {
    if (selectedIds.size === 0) return;
    bulkActionRunning = true;
    bulkMsg = 'Adding to shelf…';
    try {
      const r = await api.bulkShelfAssignment([...selectedIds], [shelfId]);
      bulkMsg = `Added ${r.assigned} books to shelf`;
    } catch (e) {
      bulkMsg = e instanceof Error ? e.message : 'Failed';
    } finally {
      bulkActionRunning = false;
      showBulkShelfPicker = false;
    }
  }
</script>

<div class="flex h-full flex-col">
  {#if !library}
    <div class="flex flex-1 items-center justify-center text-muted-foreground">Library not found</div>
  {:else}
    <!-- Header -->
    <div class="border-b px-6 py-5">
      <div class="flex items-start justify-between gap-4">
        <div class="min-w-0">
          <h1 class="font-serif text-2xl font-semibold tracking-tight text-foreground truncate">{library.name}</h1>
          {#if library.description}
            <p class="mt-0.5 text-sm text-muted-foreground">{library.description}</p>
          {/if}
          <p class="mt-1 text-xs tabular-nums text-muted-foreground/60">{total.toLocaleString()} books</p>
        </div>
        <Button variant="outline" size="sm" onclick={scan} class="shrink-0">
          <RefreshCw class="mr-1.5 h-3.5 w-3.5" /> Scan
        </Button>
      </div>

      <!-- Toolbar -->
      <div class="mt-4 flex flex-wrap items-center gap-2">
        <!-- Search -->
        <div class="relative min-w-0 flex-1 sm:max-w-xs">
          <Search class="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground/50" />
          <Input
            value={searchInput}
            oninput={onSearchInput}
            placeholder="Search this library…"
            class="h-8 pl-8 text-sm"
          />
        </div>

        <!-- Sort (hidden when grouped — grouping always sorts by title) -->
        {#if !groupBy}
          <div class="flex items-center gap-1 rounded-md border bg-background px-2 h-8">
            <ArrowUpDown class="h-3.5 w-3.5 text-muted-foreground/50 shrink-0" />
            <select
              bind:value={sortBy}
              class="h-full bg-transparent text-sm text-foreground focus:outline-none cursor-pointer pr-1"
            >
              <option value="date_added">Recently Added</option>
              <option value="title">Title A–Z</option>
            </select>
          </div>
        {/if}

        <!-- Format filter -->
        <div class="flex items-center gap-1 rounded-md border bg-background px-2 h-8">
          <FileType class="h-3.5 w-3.5 text-muted-foreground/50 shrink-0" />
          <select
            bind:value={formatFilter}
            class="h-full bg-transparent text-sm text-foreground focus:outline-none cursor-pointer pr-1"
          >
            <option value="">All formats</option>
            <option value="epub">EPUB</option>
            <option value="pdf">PDF</option>
            <option value="cbz">CBZ</option>
            <option value="cbr">CBR</option>
            <option value="mobi">MOBI</option>
            <option value="azw3">AZW3</option>
            <option value="azw">AZW</option>
            <option value="fb2">FB2</option>
            <option value="djvu">DJVU</option>
            <option value="mp3">MP3</option>
            <option value="m4b">M4B</option>
          </select>
        </div>

        <!-- Group by -->
        <div class="flex items-center gap-1 rounded-md border bg-background px-1.5 h-8">
          <Layers class="h-3.5 w-3.5 text-muted-foreground/40 shrink-0 ml-0.5" />
          <button
            onclick={() => (groupBy = null)}
            class="rounded px-2 py-0.5 text-xs transition-colors {groupBy === null ? 'bg-foreground/10 text-foreground font-medium' : 'text-muted-foreground hover:text-foreground'}"
          >None</button>
          {#each GROUP_OPTIONS as opt}
            <button
              onclick={() => (groupBy = opt.value)}
              class="rounded px-2 py-0.5 text-xs transition-colors {groupBy === opt.value ? 'bg-foreground/10 text-foreground font-medium' : 'text-muted-foreground hover:text-foreground'}"
            >{opt.label}</button>
          {/each}
        </div>

        <!-- View toggle -->
        <div class="flex items-center rounded-md border bg-background">
          <button
            onclick={() => (viewMode = 'grid')}
            class="flex h-8 w-8 items-center justify-center rounded-l-md transition-colors {viewMode === 'grid' ? 'bg-foreground/10 text-foreground' : 'text-muted-foreground hover:text-foreground'}"
            title="Grid view"
          >
            <LayoutGrid class="h-3.5 w-3.5" />
          </button>
          <button
            onclick={() => (viewMode = 'list')}
            class="flex h-8 w-8 items-center justify-center rounded-r-md border-l transition-colors {viewMode === 'list' ? 'bg-foreground/10 text-foreground' : 'text-muted-foreground hover:text-foreground'}"
            title="List view"
          >
            <List class="h-3.5 w-3.5" />
          </button>
        </div>

        <!-- Select toggle -->
        <button
          onclick={() => selectionMode ? exitSelection() : (selectionMode = true)}
          class="flex h-8 items-center gap-1.5 rounded-md border bg-background px-2.5 text-sm transition-colors {selectionMode ? 'border-primary text-primary' : 'text-muted-foreground hover:text-foreground'}"
          title={selectionMode ? 'Exit selection mode' : 'Select books'}
        >
          <CheckSquare class="h-3.5 w-3.5" />
          <span class="hidden sm:inline">{selectionMode ? 'Cancel' : 'Select'}</span>
        </button>
      </div>
    </div>

    <!-- Bulk action bar (shown in selection mode) -->
    {#if selectionMode}
      <div class="flex items-center gap-3 border-b bg-muted/30 px-6 py-2">
        <span class="text-sm font-medium tabular-nums">
          {selectedIds.size} selected
        </span>
        <button onclick={selectAll} class="text-xs text-primary hover:underline">Select all</button>
        {#if selectedIds.size > 0}
          <button onclick={deselectAll} class="text-xs text-muted-foreground hover:underline">Clear</button>
        {/if}
        <div class="flex-1"></div>
        {#if bulkMsg}
          <span class="text-xs text-muted-foreground">{bulkMsg}</span>
        {/if}
        <Button
          variant="outline"
          size="sm"
          onclick={bulkExtractIdentifiers}
          disabled={selectedIds.size === 0 || bulkActionRunning}
        >
          <ScanSearch class="mr-1.5 h-3.5 w-3.5" />
          Extract IDs
        </Button>
        <Button
          variant="outline"
          size="sm"
          onclick={bulkEnrich}
          disabled={selectedIds.size === 0 || bulkActionRunning}
        >
          <Sparkles class="mr-1.5 h-3.5 w-3.5" />
          Enrich
        </Button>
        <div class="relative">
          <Button
            variant="outline"
            size="sm"
            onclick={() => { showBulkShelfPicker = !showBulkShelfPicker; if (showBulkShelfPicker) loadBulkShelves(); }}
            disabled={selectedIds.size === 0 || bulkActionRunning}
          >
            <BookMarked class="mr-1.5 h-3.5 w-3.5" />
            Shelf
          </Button>
          {#if showBulkShelfPicker}
            <div class="fixed inset-0 z-40" onclick={() => showBulkShelfPicker = false}></div>
            <div class="absolute right-0 top-full z-50 mt-1 w-48 rounded-md border bg-popover p-1 shadow-md">
              {#each bulkShelves as shelf}
                <button
                  class="w-full rounded-sm px-3 py-1.5 text-left text-sm hover:bg-accent"
                  onclick={() => bulkAddToShelf(shelf.id)}
                >{shelf.name}</button>
              {/each}
              {#if bulkShelves.length === 0}
                <p class="px-3 py-1.5 text-xs text-muted-foreground">No shelves</p>
              {/if}
            </div>
          {/if}
        </div>
        <button onclick={exitSelection} class="ml-1 rounded p-1 text-muted-foreground hover:text-foreground">
          <X class="h-4 w-4" />
        </button>
      </div>
    {/if}

    <!-- Content -->
    <div class="flex-1 overflow-y-auto px-6 py-6">
      {#if groupBy}
        <!-- Grouped view -->
        {#if loadingAll}
          <div class="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
            {#each Array(12) as _}
              <div class="aspect-2/3 animate-pulse rounded-md bg-muted"></div>
            {/each}
          </div>
        {:else}
          <GroupedBooks books={allBooks} {groupBy} mode={viewMode} search={searchInput} {selectionMode} {selectedIds} onToggleSelect={toggleSelect} />
        {/if}
      {:else}
        <!-- Paginated view -->
        {#if loading}
          <div class="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
            {#each Array(12) as _}
              <div class="aspect-2/3 animate-pulse rounded-md bg-muted"></div>
            {/each}
          </div>
        {:else}
          <BookGrid {books} mode={viewMode} {selectionMode} {selectedIds} onToggleSelect={toggleSelect} />

          <!-- Infinite scroll sentinel + status -->
          {#if books.length > 0}
            <div class="mt-8 flex flex-col items-center gap-2">
              <p class="text-xs text-muted-foreground tabular-nums">
                Showing {books.length.toLocaleString()} of {total.toLocaleString()}
              </p>
              {#if hasMore}
                <div
                  use:infiniteScroll
                  class="flex items-center justify-center py-4"
                >
                  {#if loadingMore}
                    <p class="text-xs text-muted-foreground">Loading…</p>
                  {/if}
                </div>
              {/if}
            </div>
          {/if}
        {/if}
      {/if}
    </div>
  {/if}
</div>
