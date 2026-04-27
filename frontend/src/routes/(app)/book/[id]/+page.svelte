<script lang="ts">
  import { Badge } from "$lib/components/ui/badge";
  import { Button } from "$lib/components/ui/button";
  // ScrollProgress and BlurFade removed — motion-sv incompatible with static build
  import { Card, CardContent, CardHeader, CardTitle } from "$lib/components/ui/card";
  import { Progress } from "$lib/components/ui/progress";
  import { Separator } from "$lib/components/ui/separator";
  import { BookOpen, Download, Pencil, X, Sparkles, ChevronDown, ChevronLeft, ChevronRight, Send, BookMarked, Check, Layers, Plus, Highlighter, MessageSquare, Bookmark, Trash2, CalendarCheck, Lightbulb, Package, Headphones, ScanSearch, MapPin, Quote, Globe, FileText, Replace } from "lucide-svelte";
  import BookAnalysis from "$lib/components/BookAnalysis.svelte";
  import Marginalia from "$lib/components/Marginalia.svelte";
  import EsotericAnalysis from "$lib/components/EsotericAnalysis.svelte";
  import LiteraryAnalysis from "$lib/components/LiteraryAnalysis.svelte";
  import BookMetaEditor from "$lib/components/BookMetaEditor.svelte";
  import { bookCoverUrl, enrichBook, getEnrichmentProviders, convertBookFile, bookFileUrl, sendBookToDevice, setBookStatus, getShelves, getBookShelves, addBookToShelf, removeBookFromShelf, getCollections, addBookToCollection, removeBookFromCollection, getAnnotations, createAnnotation, deleteAnnotation, getReadSessions, createReadSession, deleteReadSession, setCoverFromUrl, setLockedFields, setEsotericEnabled, exportAnnotations, getBookRecommendations, updateBook, extractBookIdentifiers, citationUrl, computeReadingLevel, getBook, getSeriesNeighbors, generateMarkdown, replaceEditionFile } from "$lib/api/client";
  import type { SeriesNav } from "$lib/api/client";
  import type { EnrichmentProvider, BookRecommendation, EnrichStreamEvent } from "$lib/api/client";
  import { enrichBookStream } from "$lib/api/client";
  import type { Book, Shelf, Collection, Annotation, ReadSession, User } from "$lib/types/index";
  import type { PageData } from './$types';
  import { sanitizeHtml } from "$lib/utils/sanitizeHtml";

  let { data }: { data: PageData } = $props();
  let book = $state<Book | null>(data.book ?? null);
  let progress = $state(data.progress ?? null);
  let currentUser = $state<User | null>(data.user ?? null);
  let isAdmin = $derived(currentUser?.is_admin ?? false);
  let editing = $state(false);
  let absUrl = $derived((data as any).absUrl as string | null ?? null);

  // Reading status & rating
  let currentStatus = $derived(progress?.status ?? null);
  let currentRating = $state(progress?.rating ?? null);
  let statusSaving = $state(false);

  const STATUS_OPTIONS = [
    { value: 'want_to_read', label: 'Want to Read' },
    { value: 'reading',      label: 'Reading' },
    { value: 'completed',    label: 'Completed' },
    { value: 'abandoned',    label: 'Abandoned' },
  ] as const;

  async function handleStatusChange(newStatus: string) {
    if (!book) return;
    statusSaving = true;
    try {
      await setBookStatus(book.id, newStatus, currentRating);
      progress = { ...(progress ?? { current_page: 0, total_pages: null, percentage: 0, last_opened: new Date().toISOString() }), status: newStatus as any, rating: currentRating };
    } finally {
      statusSaving = false;
    }
  }

  async function handleRating(star: number) {
    if (!book) return;
    const newRating = currentRating === star ? null : star;
    currentRating = newRating;
    const statusToSend = currentStatus ?? 'want_to_read';
    try {
      await setBookStatus(book.id, statusToSend, newRating);
      if (!progress) {
        progress = { current_page: 0, total_pages: null, percentage: 0, last_opened: new Date().toISOString(), status: statusToSend as any, rating: newRating };
      } else {
        progress = { ...progress, rating: newRating };
      }
    } catch { /* non-critical */ }
  }
  let enriching = $state(false);
  let enrichError = $state('');
  let enrichSuccess = $state('');
  let showUrlEnrich = $state(false);
  let urlEnrichInput = $state('');
  let urlEnriching = $state(false);
  let providers = $state<EnrichmentProvider[]>([]);
  let selectedProvider = $state('');
  let showProviders = $state(false);
  let enrichEvents = $state<Array<{ provider: string; status: string; fields: string[]; has_cover: boolean }>>([]);
  let proposals = $state<Array<Record<string, any>>>([]);
  let loadingProposals = $state(false);
  let showProposals = $state(false);

  async function loadProposals() {
    if (!book) return;
    loadingProposals = true;
    showProposals = true;
    try {
      const { getEnrichmentProposals } = await import('$lib/api/client');
      proposals = await getEnrichmentProposals(book.id);
    } catch { proposals = []; }
    finally { loadingProposals = false; }
  }

  async function applyProposal(providerName: string) {
    if (!book) return;
    enriching = true;
    try {
      book = await enrichBook(book.id, providerName);
      enrichSuccess = `Applied metadata from ${providerName}`;
      showProposals = false;
    } catch (err) {
      enrichError = err instanceof Error ? err.message : 'Failed';
    } finally { enriching = false; }
  }

  let extractingIds = $state(false);
  let extractIdsMsg = $state('');
  let generatingMd = $state(false);
  let mdMsg = $state('');
  let replacingFile = $state(false);
  let replaceFileMsg = $state('');
  let replaceFileInput: HTMLInputElement;
  let showCiteMenu = $state(false);
  let computingFk = $state(false);
  let seriesNav = $state<SeriesNav[]>([]);

  // Load series navigation when book changes
  $effect(() => {
    if (book?.series?.length) {
      getSeriesNeighbors(book.id).then(r => seriesNav = r.series).catch(() => {});
    } else {
      seriesNav = [];
    }
  });

  let coverUrl = $derived(book ? bookCoverUrl(book) : null);
  let showCoverUrlInput = $state(false);
  let coverUrlInput = $state('');
  let showCoverPicker = $state(false);
  let coverOptions = $state<Array<{ provider: string; url: string }>>([]);
  let loadingCovers = $state(false);
  let applyingCover = $state('');

  async function loadCoverOptions() {
    if (!book) return;
    showCoverPicker = true;
    loadingCovers = true;
    try {
      const { searchCovers } = await import('$lib/api/client');
      coverOptions = await searchCovers(book.id);
    } catch { coverOptions = []; }
    finally { loadingCovers = false; }
  }

  async function applyCover(url: string, provider: string) {
    if (!book) return;
    applyingCover = provider;
    try {
      const updated = await setCoverFromUrl(book.id, url);
      book = updated;
      showCoverPicker = false;
    } catch { /* non-critical */ }
    finally { applyingCover = ''; }
  }
  let settingCoverUrl = $state(false);

  async function applyUrlCover() {
    if (!book || !coverUrlInput.trim()) return;
    settingCoverUrl = true;
    try {
      const updated = await setCoverFromUrl(book.id, coverUrlInput.trim());
      book = { ...book, cover_hash: updated.cover_hash, cover_format: updated.cover_format };
      coverUrlInput = '';
      showCoverUrlInput = false;
    } catch (e) { alert(e instanceof Error ? e.message : 'Failed'); }
    finally { settingCoverUrl = false; }
  }
  let primaryAuthor = $derived(book?.authors?.[0]?.name ?? null);
  let primaryFile = $derived(book?.files?.[0] ?? null);
  let bookId = $derived(String(book?.id ?? ''));

  let showSendDialog = $state(false);
  let sendRecipient = $state('');
  let sending = $state(false);
  let sendMsg = $state('');

  // Shelf management
  let showShelfMenu = $state(false);
  let shelves = $state<Shelf[]>([]);
  let bookShelfIds = $state<Set<number>>(new Set());
  let shelvesLoaded = $state(false);

  async function loadShelfData() {
    if (shelvesLoaded || !book) return;
    shelvesLoaded = true;
    try {
      const [all, bookShelves] = await Promise.all([
        getShelves(),
        getBookShelves(book.id),
      ]);
      shelves = all.filter(s => !s.is_smart);
      bookShelfIds = new Set(bookShelves.map(s => s.id));
    } catch { /* ignore */ }
  }

  async function toggleShelf(shelf: Shelf) {
    if (!book) return;
    const onShelf = bookShelfIds.has(shelf.id);
    try {
      if (onShelf) {
        await removeBookFromShelf(shelf.id, book.id);
        bookShelfIds = new Set([...bookShelfIds].filter(id => id !== shelf.id));
      } else {
        await addBookToShelf(shelf.id, book.id);
        bookShelfIds = new Set([...bookShelfIds, shelf.id]);
      }
    } catch { /* ignore */ }
  }

  async function handleSend() {
    if (!book || !sendRecipient.trim()) return;
    sending = true;
    sendMsg = '';
    try {
      await sendBookToDevice(book.id, sendRecipient.trim());
      sendMsg = `Sent to ${sendRecipient}`;
      setTimeout(() => { showSendDialog = false; sendMsg = ''; }, 2000);
    } catch (err) {
      sendMsg = err instanceof Error ? err.message : 'Send failed';
    } finally {
      sending = false;
    }
  }

  function handleSave(updated: Book) {
    book = updated;
    editing = false;
  }

  async function loadProviders() {
    try {
      providers = await getEnrichmentProviders();
    } catch { /* non-critical */ }
  }

  async function handleEnrich() {
    if (!book) return;
    enriching = true;
    enrichError = '';
    enrichSuccess = '';
    enrichEvents = [];

    if (selectedProvider) {
      // Direct single-provider enrich (no streaming)
      try {
        book = await enrichBook(book.id, selectedProvider);
        enrichSuccess = 'Metadata updated successfully';
        showProviders = false;
      } catch (err) {
        enrichError = err instanceof Error ? err.message : 'Enrichment failed';
      } finally {
        enriching = false;
      }
    } else {
      // Stream results from all providers via SSE
      enrichBookStream(
        book.id,
        (event) => {
          if (!event.event) {
            enrichEvents = [...enrichEvents, event];
          }
        },
        async () => {
          // SSE done — now apply via POST
          try {
            book = await enrichBook(book!.id);
            const found = enrichEvents.filter(e => e.status === 'ok' && e.fields.length > 0).length;
            enrichSuccess = `Done — ${found} provider${found !== 1 ? 's' : ''} returned data`;
          } catch (err) {
            enrichError = err instanceof Error ? err.message : 'Enrichment failed';
          } finally {
            enriching = false;
          }
        }
      );
    }
  }

  async function handleExtractIdentifiers() {
    if (!book) return;
    extractingIds = true;
    extractIdsMsg = '';
    try {
      const ids = await extractBookIdentifiers(book.id);
      const parts: string[] = [];
      if (ids.isbn_13) parts.push(`ISBN: ${ids.isbn_13}`);
      if (ids.doi) parts.push(`DOI: ${ids.doi}`);
      extractIdsMsg = parts.length ? `Found ${parts.join(', ')}` : 'No identifiers found in file content';
      // Refresh book data to show updated ISBN/DOI
      if (ids.isbn_13 || ids.doi) {
        const { getBook } = await import('$lib/api/client');
        book = await getBook(book.id);
      }
    } catch (err) {
      extractIdsMsg = err instanceof Error ? err.message : 'Extraction failed';
    } finally {
      extractingIds = false;
    }
  }

  async function handleGenerateMarkdown(force = false) {
    if (!book) return;
    generatingMd = true;
    mdMsg = '';
    try {
      const res = await generateMarkdown(book.id, force);
      mdMsg = `Markdown generated (${Math.round(res.length / 1024)}k chars)`;
    } catch (err) {
      mdMsg = err instanceof Error ? err.message : 'Generation failed';
    } finally {
      generatingMd = false;
    }
  }

  async function handleReplaceFile() {
    if (!book || !replaceFileInput?.files?.length) return;
    const primaryFile = book.files?.[0];
    if (!primaryFile) return;
    replacingFile = true;
    replaceFileMsg = '';
    try {
      const res = await replaceEditionFile(book.id, primaryFile.id, replaceFileInput.files[0]);
      replaceFileMsg = `Replaced — ${Math.round(res.file_size / 1024)}KB`;
      book = await getBook(book.id);
    } catch (err) {
      replaceFileMsg = err instanceof Error ? err.message : 'Replace failed';
    } finally {
      replacingFile = false;
    }
  }

  async function handleUrlEnrich() {
    if (!book || !urlEnrichInput.trim()) return;
    urlEnriching = true;
    enrichError = '';
    enrichSuccess = '';
    try {
      const { enrichBookFromUrl } = await import('$lib/api/client');
      book = await enrichBookFromUrl(book.id, urlEnrichInput.trim());
      enrichSuccess = 'Metadata updated from URL';
      showUrlEnrich = false;
      urlEnrichInput = '';
    } catch (err) {
      enrichError = err instanceof Error ? err.message : 'URL enrichment failed';
    } finally {
      urlEnriching = false;
    }
  }

  async function handleConvert(format: string) {
    if (!book || !primaryFile) return;
    try {
      book = await convertBookFile(book.id, primaryFile.id, format);
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Conversion failed');
    }
  }

  // ── Collections ────────────────────────────────────────────────────────────
  let showCollectionMenu = $state(false);
  let collections = $state<Collection[]>([]);
  let collectionsLoaded = $state(false);

  async function loadCollectionData() {
    if (collectionsLoaded || !book) return;
    collectionsLoaded = true;
    try { collections = await getCollections(); } catch { /* ignore */ }
  }

  async function addToCollection(collId: number) {
    if (!book) return;
    try { await addBookToCollection(collId, book.id); } catch { /* ignore */ }
    showCollectionMenu = false;
  }

  // ── Annotations ──────────────────────────────────────────────
  let annotations = $state<Annotation[]>([]);
  let annotationsLoaded = $state(false);
  let showAnnotations = $state(false);
  let newNoteText = $state('');
  let addingNote = $state(false);
  let addingBookmark = $state(false);

  async function loadAnnotations() {
    if (annotationsLoaded || !book) return;
    annotationsLoaded = true;
    try { annotations = await getAnnotations(book.id); } catch { /* ignore */ }
  }

  async function addNote() {
    if (!book || !newNoteText.trim()) return;
    addingNote = true;
    try {
      const a = await createAnnotation({ book_id: book.id, type: 'note', content: newNoteText.trim() });
      annotations = [...annotations, a];
      newNoteText = '';
    } catch { /* ignore */ } finally { addingNote = false; }
  }

  async function addBookmark() {
    if (!book) return;
    addingBookmark = true;
    try {
      const a = await createAnnotation({ book_id: book.id, type: 'bookmark' });
      annotations = [...annotations, a];
    } catch { /* ignore */ } finally { addingBookmark = false; }
  }

  async function removeAnnotation(id: number) {
    try { await deleteAnnotation(id); annotations = annotations.filter(a => a.id !== id); }
    catch { /* ignore */ }
  }

  $effect(() => {
    if (showAnnotations) loadAnnotations();
  });

  const annColorBar: Record<string, string> = {
    yellow: 'bg-yellow-400/80', green: 'bg-green-400/80',
    blue: 'bg-blue-400/80', pink: 'bg-pink-400/80', purple: 'bg-purple-400/80',
  };

  // ── Read Sessions ──────────────────────────────────────────────────────────
  let readSessions = $state<ReadSession[]>([]);
  let sessionsLoaded = $state(false);
  let showSessionLog = $state(false);
  let sessionStart = $state('');
  let sessionEnd = $state('');
  let sessionNotes = $state('');
  let sessionRating = $state<number | null>(null);
  let loggingSession = $state(false);

  async function loadSessions() {
    if (sessionsLoaded || !book) return;
    sessionsLoaded = true;
    try { readSessions = await getReadSessions(book.id); } catch { /* ignore */ }
  }

  async function logSession() {
    if (!book || !sessionStart) return;
    loggingSession = true;
    try {
      const s = await createReadSession({
        book_id: book.id,
        started_at: new Date(sessionStart).toISOString(),
        finished_at: sessionEnd ? new Date(sessionEnd).toISOString() : null,
        rating: sessionRating,
        notes: sessionNotes.trim() || null,
      });
      readSessions = [s, ...readSessions];
      sessionStart = ''; sessionEnd = ''; sessionNotes = ''; sessionRating = null;
      showSessionLog = false;
    } catch (e) { alert(e instanceof Error ? e.message : 'Failed'); }
    finally { loggingSession = false; }
  }

  async function removeSession(id: number) {
    try {
      await deleteReadSession(id);
      readSessions = readSessions.filter(s => s.id !== id);
    } catch { /* ignore */ }
  }

  $effect(() => {
    if (showSessionLog) loadSessions();
  });

  // ── Recommendations ────────────────────────────────────────────────────────
  let recommendations = $state<BookRecommendation[]>([]);
  let recsLoaded = $state(false);
  let showRecs = $state(false);

  async function loadRecs() {
    if (recsLoaded || !book) return;
    recsLoaded = true;
    try {
      recommendations = await getBookRecommendations(book.id);
    } catch { /* non-critical */ }
  }

  $effect(() => {
    if (showRecs) loadRecs();
  });

  // ── Physical copy toggle ────────────────────────────────────────────────────
  let togglingPhysical = $state(false);

  async function togglePhysicalCopy() {
    if (!book) return;
    togglingPhysical = true;
    try {
      const updated = await updateBook(book.id, { physical_copy: !book.physical_copy });
      book = updated;
    } catch { /* non-critical */ } finally { togglingPhysical = false; }
  }
</script>

{#if book}
  <!-- ColorScape gradient accent from cover -->
  {#if book.cover_color}
    <div
      class="h-32 -mb-24 opacity-20 dark:opacity-10"
      style="background: linear-gradient(to bottom, {book.cover_color}, transparent)"
    ></div>
  {/if}
  <div class="relative mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:px-8">
    {#if editing}
      <Card>
        <CardHeader class="flex flex-row items-center justify-between">
          <CardTitle>Edit Metadata</CardTitle>
          <Button variant="ghost" size="icon" onclick={() => editing = false}>
            <X class="h-4 w-4" />
          </Button>
        </CardHeader>
        <CardContent>
          <BookMetaEditor {book} onSave={handleSave} onCancel={() => editing = false} />
        </CardContent>
      </Card>
    {:else}
      <div class="grid grid-cols-1 gap-8 md:grid-cols-3">
        <!-- Cover -->
        <div class="md:col-span-1">
          <div class="aspect-2/3 overflow-hidden rounded-lg bg-muted shadow-lg">
            {#if coverUrl}
              <img src={coverUrl} alt={book.title} class="h-full w-full object-cover" />
            {:else}
              <div class="flex h-full w-full items-center justify-center">
                <BookOpen class="h-16 w-16 text-muted-foreground" />
              </div>
            {/if}
          </div>
          <div class="mt-1 flex justify-center gap-3">
            <button onclick={loadCoverOptions} class="text-[11px] text-muted-foreground/50 hover:text-muted-foreground transition-colors">
              {loadingCovers ? 'searching…' : 'browse covers'}
            </button>
            <button onclick={() => showCoverUrlInput = !showCoverUrlInput} class="text-[11px] text-muted-foreground/50 hover:text-muted-foreground transition-colors">
              paste URL
            </button>
          </div>
          {#if showCoverUrlInput}
            <div class="mt-2 flex gap-1">
              <input type="url" placeholder="Image URL…" bind:value={coverUrlInput}
                class="flex-1 min-w-0 rounded border bg-background px-2 py-1 text-xs outline-none focus:ring-1 focus:ring-ring"
                onkeydown={(e) => { if (e.key === 'Enter') applyUrlCover(); if (e.key === 'Escape') showCoverUrlInput = false; }} />
              <Button size="sm" variant="outline" class="h-7 px-2 text-xs" onclick={applyUrlCover} disabled={settingCoverUrl || !coverUrlInput.trim()}>Set</Button>
              <Button size="sm" variant="ghost" class="h-7 px-2 text-xs" onclick={() => showCoverUrlInput = false}>✕</Button>
            </div>
          {/if}
          {#if showCoverPicker}
            <div class="mt-3 space-y-2">
              {#if loadingCovers}
                <p class="text-xs text-muted-foreground text-center">Searching providers…</p>
              {:else if coverOptions.length === 0}
                <p class="text-xs text-muted-foreground text-center">No covers found</p>
              {:else}
                <div class="grid grid-cols-2 gap-2">
                  {#each coverOptions as opt}
                    <button
                      class="group relative overflow-hidden rounded-md border hover:border-primary transition-colors {applyingCover === opt.provider ? 'opacity-50' : ''}"
                      onclick={() => applyCover(opt.url, opt.provider)}
                      disabled={!!applyingCover}
                    >
                      <img src={opt.url} alt={opt.provider} class="aspect-2/3 w-full object-cover" />
                      <span class="absolute bottom-0 left-0 right-0 bg-black/60 px-1.5 py-0.5 text-[10px] text-white capitalize">
                        {applyingCover === opt.provider ? 'applying…' : opt.provider}
                      </span>
                    </button>
                  {/each}
                </div>
              {/if}
              <button onclick={() => showCoverPicker = false} class="w-full text-center text-[10px] text-muted-foreground/40 hover:text-muted-foreground">close</button>
            </div>
          {/if}
          <div class="mt-4 flex gap-2">
            {#if primaryFile}
              <Button class="flex-1" href="/reader/{book.id}">
                <BookOpen class="mr-2 h-4 w-4" /> Read
              </Button>
              <Button variant="outline" size="icon" title="Download" href={bookFileUrl(book.id, primaryFile.id)}>
                <Download class="h-4 w-4" />
              </Button>
              {#if isAdmin}
                <input
                  type="file"
                  accept=".epub,.pdf,.cbz,.cbr,.mobi,.azw,.azw3"
                  class="hidden"
                  bind:this={replaceFileInput}
                  onchange={handleReplaceFile}
                />
                <Button
                  variant="outline"
                  size="icon"
                  title={replacingFile ? 'Replacing…' : 'Replace file'}
                  disabled={replacingFile}
                  onclick={() => replaceFileInput?.click()}
                >
                  <Replace class="h-4 w-4" />
                </Button>
              {/if}
              <Button variant="outline" size="icon" title="Send to device" onclick={() => showSendDialog = true}>
                <Send class="h-4 w-4" />
              </Button>
            {:else}
              <Button class="flex-1" disabled>
                <BookOpen class="mr-2 h-4 w-4" /> Read
              </Button>
            {/if}
            <!-- Add to shelf -->
            <div class="relative">
              <Button
                variant="outline"
                size="icon"
                title="Add to shelf"
                onclick={() => { showShelfMenu = !showShelfMenu; loadShelfData(); }}
              >
                <BookMarked class="h-4 w-4" />
              </Button>
              {#if showShelfMenu}
                <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
                <div class="fixed inset-0 z-40" onclick={() => showShelfMenu = false}></div>
                <div class="absolute right-0 top-full z-50 mt-1 w-52 rounded-md border bg-popover p-1 shadow-md">
                  {#if shelves.length === 0}
                    <p class="px-3 py-2 text-xs text-muted-foreground">No shelves yet. <a href="/shelves" class="underline">Create one</a>.</p>
                  {:else}
                    {#each shelves as shelf}
                      <button
                        class="flex w-full items-center gap-2 rounded-sm px-3 py-1.5 text-left text-sm hover:bg-accent"
                        onclick={() => toggleShelf(shelf)}
                      >
                        <span class="flex h-4 w-4 items-center justify-center rounded-sm border {bookShelfIds.has(shelf.id) ? 'border-foreground bg-foreground' : 'border-border'}">
                          {#if bookShelfIds.has(shelf.id)}
                            <Check class="h-3 w-3 text-background" />
                          {/if}
                        </span>
                        {shelf.name}
                      </button>
                    {/each}
                    <div class="my-1 border-t"></div>
                    <a href="/shelves" class="flex items-center gap-2 rounded-sm px-3 py-1.5 text-xs text-muted-foreground hover:bg-accent hover:text-foreground">
                      Manage shelves →
                    </a>
                  {/if}
                </div>
              {/if}
            </div>

            <!-- Add to collection -->
            <div class="relative">
              <Button variant="outline" size="icon" title="Add to collection"
                onclick={() => { showCollectionMenu = !showCollectionMenu; loadCollectionData(); }}>
                <Layers class="h-4 w-4" />
              </Button>
              {#if showCollectionMenu}
                <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
                <div class="fixed inset-0 z-40" onclick={() => showCollectionMenu = false}></div>
                <div class="absolute right-0 top-full z-50 mt-1 w-52 rounded-md border bg-popover p-1 shadow-md">
                  {#if collections.length === 0}
                    <p class="px-3 py-2 text-xs text-muted-foreground">No collections. <a href="/collections" class="underline">Create one</a>.</p>
                  {:else}
                    {#each collections as col}
                      <button class="flex w-full items-center gap-2 rounded-sm px-3 py-1.5 text-left text-sm hover:bg-accent"
                        onclick={() => addToCollection(col.id)}>
                        <Layers class="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                        {col.name}
                      </button>
                    {/each}
                  {/if}
                </div>
              {/if}
            </div>
          </div>

          <!-- Reading status -->
          <div class="mt-4 space-y-3">
            <div class="flex flex-wrap gap-1.5">
              {#each STATUS_OPTIONS as opt}
                <button
                  onclick={() => handleStatusChange(opt.value)}
                  disabled={statusSaving}
                  class="rounded-full border px-3 py-1 text-xs font-medium transition-colors {currentStatus === opt.value
                    ? 'border-foreground bg-foreground text-background'
                    : 'border-border bg-transparent text-muted-foreground hover:border-foreground/50 hover:text-foreground'}"
                >
                  {opt.label}
                </button>
              {/each}
            </div>

            <!-- Star rating -->
            <div class="flex items-center gap-0.5" aria-label="Rating">
              {#each [1, 2, 3, 4, 5] as star}
                <button
                  onclick={() => handleRating(star)}
                  class="p-0.5 text-lg leading-none transition-colors {(currentRating ?? 0) >= star ? 'text-amber-400' : 'text-muted-foreground/30 hover:text-amber-300'}"
                  title="{star} star{star > 1 ? 's' : ''}"
                  aria-label="{star} star{star > 1 ? 's' : ''}"
                >★</button>
              {/each}
              {#if currentRating}
                <span class="ml-1.5 text-xs text-muted-foreground">{currentRating}/5</span>
              {/if}
            </div>

            <!-- Physical copy indicator -->
            <div class="flex items-center gap-2">
              {#if book.physical_copy}
                <span class="flex items-center gap-1.5 rounded-full border border-amber-300/50 bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700 dark:border-amber-700/50 dark:bg-amber-950/40 dark:text-amber-400">
                  <Package class="h-3 w-3" /> Physical copy
                </span>
              {/if}
              {#if book.binding}
                <span class="rounded-full border px-2.5 py-1 text-xs text-muted-foreground capitalize">{book.binding.replace('_', ' ')}</span>
              {/if}
              {#if book.condition}
                <span class="rounded-full border px-2.5 py-1 text-xs text-muted-foreground capitalize">{book.condition.replace('_', ' ')}</span>
              {/if}
              {#if book.location_name}
                <span class="flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs text-muted-foreground">
                  <MapPin class="h-3 w-3" />
                  {book.location_name}
                </span>
              {/if}
              {#if isAdmin}
                <button
                  onclick={togglePhysicalCopy}
                  disabled={togglingPhysical}
                  class="text-xs text-muted-foreground/60 hover:text-muted-foreground transition-colors disabled:opacity-40"
                  title={book.physical_copy ? 'Remove physical copy flag' : 'Mark as physical copy'}
                >
                  {book.physical_copy ? '− unmark' : '+ physical copy'}
                </button>
              {/if}
            </div>
          </div>

          {#if showSendDialog}
            <div class="mt-3 space-y-2 rounded-md border bg-muted/50 p-3">
              <p class="text-sm font-medium">Send to device</p>
              <input
                type="email"
                placeholder="device@kindle.com"
                bind:value={sendRecipient}
                class="w-full rounded border bg-background px-3 py-1.5 text-sm outline-none focus:ring-1 focus:ring-ring"
              />
              {#if sendMsg}
                <p class="text-xs {sendMsg.startsWith('Sent') ? 'text-green-600' : 'text-destructive'}">{sendMsg}</p>
              {/if}
              <div class="flex gap-2">
                <Button size="sm" onclick={handleSend} disabled={sending || !sendRecipient.trim()}>
                  {sending ? 'Sending...' : 'Send'}
                </Button>
                <Button size="sm" variant="outline" onclick={() => { showSendDialog = false; sendMsg = ''; }}>Cancel</Button>
              </div>
            </div>
          {/if}
        </div>

        <!-- Details -->
        <div class="md:col-span-2">
          <div class="flex items-start justify-between">
            <div>
              <h1 class="text-3xl font-bold tracking-tight">{book.title}</h1>
              {#if primaryAuthor}
                <p class="mt-1 text-lg text-muted-foreground">by {primaryAuthor}</p>
              {/if}
            </div>
            <div class="flex gap-1">
              <!-- Enrich button with provider picker -->
              <div class="relative">
                <div class="flex">
                  <Button
                    variant="outline"
                    size="sm"
                    onclick={handleEnrich}
                    disabled={enriching}
                    class="rounded-r-none border-r-0"
                    title="Enrich metadata from external sources"
                  >
                    <Sparkles class="mr-1.5 h-3.5 w-3.5" />
                    {enriching ? 'Enriching...' : 'Enrich'}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    class="rounded-l-none px-2"
                    onclick={() => { showProviders = !showProviders; if (showProviders) loadProviders(); }}
                  >
                    <ChevronDown class="h-3.5 w-3.5" />
                  </Button>
                </div>
                {#if showProviders}
                  <div class="absolute right-0 top-full z-50 mt-1 w-48 rounded-md border bg-popover p-1 shadow-md">
                    <button
                      class="w-full rounded-sm px-3 py-1.5 text-left text-sm hover:bg-accent {selectedProvider === '' ? 'font-medium' : ''}"
                      onclick={() => { selectedProvider = ''; showProviders = false; }}
                    >
                      Auto (best match)
                    </button>
                    {#each providers.filter(p => p.available) as p}
                      <button
                        class="w-full rounded-sm px-3 py-1.5 text-left text-sm capitalize hover:bg-accent {selectedProvider === p.name ? 'font-medium' : ''}"
                        onclick={() => { selectedProvider = p.name; showProviders = false; }}
                      >
                        {p.name.replace(/_/g, ' ')}
                        {#if p.for_comics}<span class="ml-1 text-xs text-muted-foreground">(comics)</span>{/if}
                      </button>
                    {/each}
                  </div>
                {/if}
              </div>
              <Button
                variant="outline"
                size="sm"
                onclick={loadProposals}
                disabled={loadingProposals}
                title="Compare metadata from all providers"
              >
                <Layers class="mr-1.5 h-3.5 w-3.5" />
                {loadingProposals ? 'Loading…' : 'Compare'}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onclick={handleExtractIdentifiers}
                disabled={extractingIds}
                title="Scan file content for ISBN & DOI"
              >
                <ScanSearch class="mr-1.5 h-3.5 w-3.5" />
                {extractingIds ? 'Scanning…' : 'Extract IDs'}
              </Button>
              {#if isAdmin}
                <div class="relative">
                  <div class="flex">
                    <Button
                      variant="outline"
                      size="sm"
                      onclick={() => handleGenerateMarkdown(false)}
                      disabled={generatingMd}
                      class="rounded-r-none border-r-0"
                      title="Generate LLM-optimized markdown from book file"
                    >
                      <FileText class="mr-1.5 h-3.5 w-3.5" />
                      {generatingMd ? 'Generating…' : 'Markdown'}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      class="rounded-l-none px-2"
                      onclick={() => handleGenerateMarkdown(true)}
                      disabled={generatingMd}
                      title="Force regenerate (overwrite existing)"
                    >
                      <Sparkles class="h-3.5 w-3.5" />
                    </Button>
                  </div>
                  {#if mdMsg}
                    <p class="absolute right-0 top-full z-10 mt-1 whitespace-nowrap rounded bg-popover px-2 py-1 text-xs shadow-md border">{mdMsg}</p>
                  {/if}
                </div>
              {/if}
              <div class="relative">
                <Button
                  variant="outline"
                  size="sm"
                  onclick={() => showUrlEnrich = !showUrlEnrich}
                  disabled={urlEnriching}
                  title="Enrich from a web page URL (Goodreads, Amazon, publisher site)"
                >
                  <Globe class="mr-1.5 h-3.5 w-3.5" />
                  {urlEnriching ? 'Fetching…' : 'From URL'}
                </Button>
                {#if showUrlEnrich}
                  <div class="fixed inset-0 z-40" onclick={() => showUrlEnrich = false}></div>
                  <div class="absolute right-0 top-full z-50 mt-1 w-80 rounded-md border bg-popover p-3 shadow-md space-y-2">
                    <p class="text-xs text-muted-foreground">Paste a Goodreads, Amazon, or publisher page URL to extract metadata</p>
                    <input
                      bind:value={urlEnrichInput}
                      placeholder="https://..."
                      class="w-full rounded border bg-background px-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-ring"
                      onkeydown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleUrlEnrich(); } }}
                    />
                    <Button size="sm" class="w-full" onclick={handleUrlEnrich} disabled={!urlEnrichInput.trim() || urlEnriching}>
                      {urlEnriching ? 'Extracting…' : 'Extract & Apply'}
                    </Button>
                  </div>
                {/if}
              </div>
              <div class="relative">
                <Button
                  variant="outline"
                  size="sm"
                  onclick={() => showCiteMenu = !showCiteMenu}
                  title="Export citation"
                >
                  <Quote class="mr-1.5 h-3.5 w-3.5" />
                  Cite
                </Button>
                {#if showCiteMenu}
                  <div class="fixed inset-0 z-40" onclick={() => showCiteMenu = false}></div>
                  <div class="absolute right-0 top-full z-50 mt-1 w-36 rounded-md border bg-popover p-1 shadow-md">
                    <a href={citationUrl(book.id, 'bibtex')} class="block w-full rounded-sm px-3 py-1.5 text-left text-sm hover:bg-accent" onclick={() => showCiteMenu = false}>BibTeX</a>
                    <a href={citationUrl(book.id, 'mla')} class="block w-full rounded-sm px-3 py-1.5 text-left text-sm hover:bg-accent" onclick={() => showCiteMenu = false}>MLA</a>
                    <a href={citationUrl(book.id, 'apa')} class="block w-full rounded-sm px-3 py-1.5 text-left text-sm hover:bg-accent" onclick={() => showCiteMenu = false}>APA</a>
                  </div>
                {/if}
              </div>
              <Button variant="ghost" size="icon" onclick={() => editing = true} title="Edit metadata">
                <Pencil class="h-4 w-4" />
              </Button>
            </div>
          </div>

          {#if enrichEvents.length > 0}
            <div class="mt-3 space-y-1">
              {#each enrichEvents as ev}
                <div class="flex items-center gap-2 text-xs">
                  <span class="w-2 h-2 rounded-full shrink-0 {ev.status === 'ok' && ev.fields.length > 0 ? 'bg-green-500' : ev.status === 'error' ? 'bg-red-400' : 'bg-muted-foreground/30'}"></span>
                  <span class="font-medium capitalize">{ev.provider}</span>
                  {#if ev.status === 'ok' && ev.fields.length > 0}
                    <span class="text-muted-foreground">{ev.fields.length} fields{ev.has_cover ? ' + cover' : ''}</span>
                  {:else if ev.status === 'ok'}
                    <span class="text-muted-foreground">no match</span>
                  {:else if ev.status === 'skipped'}
                    <span class="text-muted-foreground/50">not configured</span>
                  {:else}
                    <span class="text-red-400">error</span>
                  {/if}
                </div>
              {/each}
            </div>
          {/if}
          {#if enrichSuccess}
            <p class="mt-2 text-sm text-green-600">{enrichSuccess}</p>
          {/if}
          {#if enrichError}
            <p class="mt-2 text-sm text-destructive">{enrichError}</p>
          {/if}
          {#if extractIdsMsg}
            <p class="mt-2 text-sm text-muted-foreground">{extractIdsMsg}</p>
          {/if}
          {#if replaceFileMsg}
            <p class="mt-2 text-sm text-muted-foreground">{replaceFileMsg}</p>
          {/if}

          <!-- Metadata Proposals Panel -->
          {#if showProposals}
            <Card class="mt-4">
              <CardHeader class="pb-3">
                <div class="flex items-center justify-between">
                  <CardTitle class="text-base">Metadata Proposals</CardTitle>
                  <button onclick={() => showProposals = false} class="text-muted-foreground hover:text-foreground">
                    <X class="h-4 w-4" />
                  </button>
                </div>
              </CardHeader>
              <CardContent>
                {#if loadingProposals}
                  <p class="text-sm text-muted-foreground">Querying all providers…</p>
                {:else if proposals.length === 0}
                  <p class="text-sm text-muted-foreground">No providers returned results.</p>
                {:else}
                  <div class="overflow-x-auto">
                    <table class="w-full text-xs">
                      <thead>
                        <tr class="border-b text-left text-muted-foreground">
                          <th class="pb-2 pr-3 font-medium">Field</th>
                          {#each proposals as p}
                            <th class="pb-2 px-2 font-medium capitalize min-w-32">{p._provider}</th>
                          {/each}
                        </tr>
                      </thead>
                      <tbody>
                        {#each ['title', 'subtitle', 'description', 'authors', 'isbn', 'published_date', 'publisher', 'page_count', 'language', 'tags'] as field}
                          {@const hasAny = proposals.some(p => p[field])}
                          {#if hasAny}
                            <tr class="border-b border-muted/50">
                              <td class="py-1.5 pr-3 font-medium text-muted-foreground capitalize">{field.replace(/_/g, ' ')}</td>
                              {#each proposals as p}
                                <td class="py-1.5 px-2 max-w-48 truncate" title={String(p[field] ?? '')}>
                                  {#if field === 'description' && p[field]}
                                    <span class="text-muted-foreground">{String(p[field]).slice(0, 80)}…</span>
                                  {:else if field === 'authors' && Array.isArray(p[field])}
                                    {p[field].join(', ')}
                                  {:else if field === 'tags' && Array.isArray(p[field])}
                                    {p[field].slice(0, 5).join(', ')}
                                  {:else if field === 'published_date' && p[field]}
                                    {String(p[field]).slice(0, 10)}
                                  {:else}
                                    {p[field] ?? '—'}
                                  {/if}
                                </td>
                              {/each}
                            </tr>
                          {/if}
                        {/each}
                        <!-- Ratings row -->
                        {#if proposals.some(p => p.goodreads_rating || p.amazon_rating)}
                          <tr class="border-b border-muted/50">
                            <td class="py-1.5 pr-3 font-medium text-muted-foreground">Ratings</td>
                            {#each proposals as p}
                              <td class="py-1.5 px-2">
                                {#if p.goodreads_rating}GR: {p.goodreads_rating}{p.goodreads_rating_count ? ` (${p.goodreads_rating_count})` : ''}{/if}
                                {#if p.amazon_rating}{p.goodreads_rating ? ' · ' : ''}AMZ: {p.amazon_rating}{/if}
                                {#if !p.goodreads_rating && !p.amazon_rating}—{/if}
                              </td>
                            {/each}
                          </tr>
                        {/if}
                        <!-- Cover row -->
                        {#if proposals.some(p => p.cover_url)}
                          <tr class="border-b border-muted/50">
                            <td class="py-1.5 pr-3 font-medium text-muted-foreground">Cover</td>
                            {#each proposals as p}
                              <td class="py-1.5 px-2">
                                {#if p.cover_url}
                                  <img src={p.cover_url} alt="" class="h-16 w-auto rounded" />
                                {:else}—{/if}
                              </td>
                            {/each}
                          </tr>
                        {/if}
                      </tbody>
                    </table>
                  </div>
                  <!-- Apply buttons -->
                  <div class="mt-3 flex gap-2 flex-wrap">
                    {#each proposals as p}
                      <Button
                        variant="outline"
                        size="sm"
                        onclick={() => applyProposal(p._provider)}
                        disabled={enriching}
                        class="capitalize"
                      >
                        Apply {p._provider}
                      </Button>
                    {/each}
                  </div>
                {/if}
              </CardContent>
            </Card>
          {/if}

          {#if book.series?.length}
            <div class="mt-3 flex flex-wrap gap-2">
              {#each book.series as s}
                <a href="/browse/series/{s.id}">
                  <Badge variant="outline" class="cursor-pointer hover:bg-accent">{s.name}</Badge>
                </a>
              {/each}
            </div>
          {/if}

          <!-- Series navigation -->
          {#each seriesNav as nav}
            <div class="mt-3 flex items-center gap-2 rounded-lg border bg-muted/30 px-3 py-2 text-sm">
              {#if nav.previous}
                <a href="/book/{nav.previous.id}" class="flex items-center gap-1 text-muted-foreground hover:text-foreground transition-colors" title={nav.previous.title}>
                  <ChevronLeft class="h-4 w-4" />
                  <span class="hidden sm:inline truncate max-w-32">{nav.previous.title}</span>
                </a>
              {:else}
                <span class="w-4"></span>
              {/if}
              <div class="flex-1 text-center text-xs text-muted-foreground">
                <a href="/browse/series/{nav.series_id}" class="hover:text-foreground transition-colors">
                  {nav.series_name}
                </a>
                {#if nav.current_position} · #{nav.current_position}{/if}
                <span class="text-muted-foreground/50">of {nav.total}</span>
              </div>
              {#if nav.next}
                <a href="/book/{nav.next.id}" class="flex items-center gap-1 text-muted-foreground hover:text-foreground transition-colors" title={nav.next.title}>
                  <span class="hidden sm:inline truncate max-w-32">{nav.next.title}</span>
                  <ChevronRight class="h-4 w-4" />
                </a>
              {:else}
                <span class="w-4"></span>
              {/if}
            </div>
          {/each}

          {#if book.abs_item_id && absUrl}
            <div class="mt-3">
              <a
                href="{absUrl}/item/{book.abs_item_id}"
                target="_blank"
                rel="noopener noreferrer"
                class="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm font-medium text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors"
              >
                <Headphones class="h-3.5 w-3.5" />
                Open audiobook
              </a>
            </div>
          {:else if book.abs_item_id}
            <div class="mt-3">
              <span class="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm text-muted-foreground">
                <Headphones class="h-3.5 w-3.5" />
                Audiobook linked
              </span>
            </div>
          {/if}

          {#if book.description}
            <!-- book.description comes from external metadata providers
                 (Google Books, Open Library, Hardcover, Goodreads, ISBNDB,
                 LibraryThing). Sanitize before {@html} render to block
                 stored XSS via a malicious / compromised provider. -->
            <div class="mt-4 leading-relaxed text-muted-foreground prose prose-sm dark:prose-invert max-w-none [&>br]:block [&>br]:mt-2">{@html sanitizeHtml(book.description)}</div>
          {/if}

          <Separator class="my-6" />

          <!-- Metadata grid -->
          <div class="grid grid-cols-2 gap-4">
            {#if book.isbn}
              <div>
                <p class="text-sm text-muted-foreground">ISBN</p>
                <p class="text-lg font-semibold">{book.isbn}</p>
                {#if book.isbn_10}
                  <p class="text-xs text-muted-foreground">ISBN-10: {book.isbn_10}</p>
                {/if}
              </div>
            {/if}
            {#if book.asin}
              <div>
                <p class="text-sm text-muted-foreground">ASIN</p>
                <a href="https://www.amazon.com/dp/{book.asin}" target="_blank" rel="noopener noreferrer"
                   class="text-lg font-semibold text-primary hover:underline">{book.asin}</a>
              </div>
            {/if}
            {#if book.doi}
              <div>
                <p class="text-sm text-muted-foreground">DOI</p>
                <a href="https://doi.org/{book.doi}" target="_blank" rel="noopener noreferrer"
                   class="text-sm font-semibold text-primary hover:underline break-all">{book.doi}</a>
              </div>
            {/if}
            {#if book.published_date}
              <div>
                <p class="text-sm text-muted-foreground">Published</p>
                <p class="text-lg font-semibold">{new Date(book.published_date).toLocaleDateString()}</p>
              </div>
            {/if}
            {#if book.language}
              <div>
                <p class="text-sm text-muted-foreground">Language</p>
                <p class="text-lg font-semibold">{book.language}</p>
              </div>
            {/if}
            {#if book.files?.length}
              {@const uniqueFormats = [...new Map(book.files.map(f => [f.format.toLowerCase(), f])).values()]}
              <div>
                <p class="text-sm text-muted-foreground">Format{uniqueFormats.length > 1 ? 's' : ''} ({book.files.length} file{book.files.length > 1 ? 's' : ''})</p>
                <div class="flex flex-wrap gap-1.5 mt-0.5">
                  {#each uniqueFormats as f}
                    <span class="rounded bg-secondary px-2 py-0.5 text-sm font-semibold uppercase">{f.format}</span>
                  {/each}
                  {#if book.abs_item_id}
                    <span class="flex items-center gap-1 rounded bg-secondary px-2 py-0.5 text-sm font-semibold">
                      <Headphones class="h-3.5 w-3.5" />
                      Audio
                    </span>
                  {/if}
                </div>
              </div>
            {:else if book.abs_item_id}
              <div>
                <p class="text-sm text-muted-foreground">Format</p>
                <div class="flex flex-wrap gap-1.5 mt-0.5">
                  <span class="flex items-center gap-1 rounded bg-secondary px-2 py-0.5 text-sm font-semibold">
                    <Headphones class="h-3.5 w-3.5" />
                    Audio
                  </span>
                </div>
              </div>
            {/if}
          </div>

          <!-- Reading Levels -->
          {#if book.lexile || book.ar_level || book.flesch_kincaid_grade || book.age_range || isAdmin}
            <div class="mt-4 flex flex-wrap items-center gap-2">
              {#if book.lexile}
                <span class="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700 dark:border-blue-800 dark:bg-blue-950/40 dark:text-blue-400">
                  Lexile {book.lexile}L{#if book.lexile_code} ({book.lexile_code}){/if}
                </span>
              {/if}
              {#if book.ar_level}
                <span class="rounded-full border border-purple-200 bg-purple-50 px-2.5 py-1 text-xs font-medium text-purple-700 dark:border-purple-800 dark:bg-purple-950/40 dark:text-purple-400">
                  AR {book.ar_level}{#if book.ar_points} · {book.ar_points} pts{/if}
                </span>
              {/if}
              {#if book.flesch_kincaid_grade}
                <span class="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-400">
                  FK Grade {book.flesch_kincaid_grade}
                </span>
              {/if}
              {#if book.age_range}
                <span class="rounded-full border px-2.5 py-1 text-xs font-medium text-muted-foreground">
                  Ages {book.age_range}
                </span>
              {/if}
              {#if book.interest_level}
                <span class="rounded-full border px-2.5 py-1 text-xs font-medium text-muted-foreground">
                  {book.interest_level}
                </span>
              {/if}
              {#if isAdmin && !book.flesch_kincaid_grade}
                <button
                  class="rounded-full border border-dashed px-2.5 py-1 text-xs text-muted-foreground/60 hover:text-muted-foreground hover:border-muted-foreground transition-colors disabled:opacity-40"
                  disabled={computingFk}
                  onclick={async () => {
                    computingFk = true;
                    try {
                      const r = await computeReadingLevel(book.id);
                      if (r.flesch_kincaid_grade) {
                        book = await getBook(book.id);
                      }
                    } catch { /* ignore */ }
                    computingFk = false;
                  }}
                >
                  {computingFk ? 'Computing…' : '+ Compute FK Grade'}
                </button>
              {/if}
            </div>
          {/if}

          <!-- Tags -->
          {#if book.tags?.length}
            <div class="mt-6 flex flex-wrap gap-2">
              {#each book.tags as tag}
                <a href="/browse/tags/{tag.id}">
                  <Badge variant="secondary" class="cursor-pointer hover:bg-secondary/80">{tag.name}</Badge>
                </a>
              {/each}
            </div>
          {/if}

          <!-- Content Warnings -->
          {#if book.content_warnings && (book.content_warnings.graphic?.length || book.content_warnings.moderate?.length || book.content_warnings.minor?.length)}
            <div class="mt-6">
              <p class="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wide">Content Warnings</p>
              <div class="flex flex-wrap gap-1.5">
                {#each book.content_warnings.graphic ?? [] as w}
                  <Badge variant="destructive" class="text-xs">{w}</Badge>
                {/each}
                {#each book.content_warnings.moderate ?? [] as w}
                  <Badge variant="outline" class="text-xs border-orange-400 text-orange-700 dark:text-orange-400">{w}</Badge>
                {/each}
                {#each book.content_warnings.minor ?? [] as w}
                  <Badge variant="outline" class="text-xs text-muted-foreground">{w}</Badge>
                {/each}
              </div>
            </div>
          {/if}

          <!-- Contributors -->
          {#each [
            { label: 'Translated by', names: book.translators },
            { label: 'Edited by', names: book.editors },
            { label: 'Illustrated by', names: book.illustrators },
            { label: 'Colors by', names: book.colorists },
          ] as contrib}
            {#if contrib.names?.length}
              <div class="mt-3 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                <span class="font-medium">{contrib.label}:</span>
                {#each contrib.names as name}
                  <span>{name}</span>
                {/each}
              </div>
            {/if}
          {/each}

          <!-- Annotations -->
          <div class="mt-6">
            <button
              class="flex w-full items-center justify-between text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
              onclick={() => { showAnnotations = !showAnnotations; }}
            >
              <span class="flex items-center gap-1.5">
                <MessageSquare class="h-3.5 w-3.5" />
                Notes & Highlights{#if annotationsLoaded && annotations.length > 0} ({annotations.length}){/if}
              </span>
              <span class="flex items-center gap-2">
                {#if book}
                  <a
                    href="/api/v1/export/books/{book.id}/annotated"
                    target="_blank"
                    class="text-[10px] text-muted-foreground hover:text-foreground underline"
                    title="Download annotated HTML edition"
                    onclick={(e) => e.stopPropagation()}
                  >annotated html</a>
                  <a
                    href="/api/v1/annotations/export?book_id={book.id}&fmt=yaml"
                    target="_blank"
                    class="text-[10px] text-muted-foreground hover:text-foreground underline"
                    title="Export as YAML"
                    onclick={(e) => e.stopPropagation()}
                  >yaml</a>
                {/if}
                <ChevronDown class="h-3.5 w-3.5 transition-transform {showAnnotations ? 'rotate-180' : ''}" />
              </span>
            </button>
            {#if showAnnotations}
              <div class="mt-3 space-y-2">
                {#if annotationsLoaded && annotations.length === 0}
                  <p class="text-xs text-muted-foreground py-2 text-center">No annotations yet.</p>
                {/if}
                {#each annotations as ann}
                  <div class="group flex items-start gap-2 rounded-md border p-3 text-sm">
                    {#if ann.type === 'highlight'}
                      <span class="mt-0.5 h-3.5 w-1 shrink-0 rounded-full {annColorBar[ann.color ?? 'yellow'] ?? annColorBar.yellow}"></span>
                    {:else if ann.type === 'bookmark'}
                      <Bookmark class="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                    {:else}
                      <MessageSquare class="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground/50" />
                    {/if}
                    <div class="flex-1 min-w-0">
                      {#if ann.chapter}<p class="text-xs text-muted-foreground mb-0.5">{ann.chapter}</p>{/if}
                      {#if ann.content}
                        <p class="text-sm {ann.type === 'highlight' ? 'italic' : ''}">{ann.content}</p>
                      {:else}
                        <p class="text-xs text-muted-foreground italic">Bookmark</p>
                      {/if}
                    </div>
                    <button class="invisible group-hover:visible text-muted-foreground/40 hover:text-destructive transition-colors"
                      onclick={() => removeAnnotation(ann.id)}>
                      <Trash2 class="h-3.5 w-3.5" />
                    </button>
                  </div>
                {/each}
                <div class="flex gap-2">
                  <input
                    type="text"
                    placeholder="Add a note…"
                    bind:value={newNoteText}
                    class="flex-1 rounded-md border bg-background px-3 py-1.5 text-sm outline-none focus:ring-1 focus:ring-ring"
                    onkeydown={(e) => { if (e.key === 'Enter') addNote(); }}
                  />
                  <Button size="sm" variant="outline" onclick={addNote} disabled={addingNote || !newNoteText.trim()}>
                    <Plus class="h-3.5 w-3.5" />
                  </Button>
                  <Button size="sm" variant="ghost" onclick={addBookmark} disabled={addingBookmark} title="Add bookmark">
                    <Bookmark class="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            {/if}
          </div>

          <!-- Read Sessions -->
          <div class="mt-4">
            <button
              class="flex w-full items-center justify-between text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
              onclick={() => { showSessionLog = !showSessionLog; }}
            >
              <span class="flex items-center gap-1.5"><CalendarCheck class="h-3.5 w-3.5" /> Reading History ({readSessions.length})</span>
              <ChevronDown class="h-3.5 w-3.5 transition-transform {showSessionLog ? 'rotate-180' : ''}" />
            </button>
            {#if showSessionLog}
              <div class="mt-3 space-y-3">
                {#each readSessions as s}
                  <div class="rounded-md border p-3 text-sm">
                    <div class="flex items-start justify-between gap-2">
                      <div class="min-w-0">
                        <p class="font-medium">
                          {new Date(s.started_at).toLocaleDateString()}
                          {#if s.finished_at} → {new Date(s.finished_at).toLocaleDateString()}{/if}
                        </p>
                        {#if s.rating}<p class="text-amber-500">{'★'.repeat(s.rating)}</p>{/if}
                        {#if s.notes}<p class="mt-1 text-muted-foreground">{s.notes}</p>{/if}
                      </div>
                      <button onclick={() => removeSession(s.id)} class="shrink-0 text-muted-foreground/40 hover:text-destructive transition-colors" title="Delete">
                        <Trash2 class="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                {/each}
                <!-- Log new session -->
                <div class="space-y-2 rounded-md border bg-muted/30 p-3">
                  <p class="text-xs font-medium text-muted-foreground">Log a read</p>
                  <div class="grid grid-cols-2 gap-2">
                    <div>
                      <label class="text-xs text-muted-foreground">Started</label>
                      <input type="date" bind:value={sessionStart}
                        class="w-full rounded border bg-background px-2 py-1 text-sm outline-none focus:ring-1 focus:ring-ring" />
                    </div>
                    <div>
                      <label class="text-xs text-muted-foreground">Finished (optional)</label>
                      <input type="date" bind:value={sessionEnd}
                        class="w-full rounded border bg-background px-2 py-1 text-sm outline-none focus:ring-1 focus:ring-ring" />
                    </div>
                  </div>
                  <div class="flex items-center gap-1">
                    {#each [1,2,3,4,5] as star}
                      <button onclick={() => sessionRating = sessionRating === star ? null : star}
                        class="text-lg {(sessionRating ?? 0) >= star ? 'text-amber-400' : 'text-muted-foreground/30 hover:text-amber-300'}">★</button>
                    {/each}
                  </div>
                  <input type="text" placeholder="Notes (optional)" bind:value={sessionNotes}
                    class="w-full rounded border bg-background px-3 py-1.5 text-sm outline-none focus:ring-1 focus:ring-ring" />
                  <Button size="sm" onclick={logSession} disabled={loggingSession || !sessionStart}>
                    {loggingSession ? 'Saving…' : 'Log Read'}
                  </Button>
                </div>
              </div>
            {/if}
          </div>

          <!-- Reading progress bar (only when actively reading) -->
          {#if progress && progress.percentage > 0}
            <div class="mt-6 space-y-1.5">
              <div class="flex items-center justify-between text-xs text-muted-foreground">
                <span>Progress</span>
                <span class="tabular-nums font-medium">{Math.round(progress.percentage)}%{#if progress.current_page && progress.total_pages} · p.{progress.current_page}/{progress.total_pages}{/if}</span>
              </div>
              <Progress value={progress.percentage} class="h-1.5" />
            </div>
          {/if}

          <!-- Recommendations -->
          <div class="mt-4">
            <button
              class="flex w-full items-center justify-between text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
              onclick={() => { showRecs = !showRecs; }}
            >
              <span class="flex items-center gap-1.5"><Lightbulb class="h-3.5 w-3.5" /> You might also like</span>
              <ChevronDown class="h-3.5 w-3.5 transition-transform {showRecs ? 'rotate-180' : ''}" />
            </button>
            {#if showRecs}
              <div class="mt-3">
                {#if !recsLoaded}
                  <p class="text-xs text-muted-foreground text-center py-2">Loading…</p>
                {:else if recommendations.length === 0}
                  <p class="text-xs text-muted-foreground text-center py-2">No similar books found in your library.</p>
                {:else}
                  <div class="space-y-1.5">
                    {#each recommendations as rec}
                      <a
                        href="/book/{rec.id}"
                        class="flex items-start gap-3 rounded-md border p-2.5 text-sm hover:bg-muted/40 transition-colors"
                      >
                        <div class="min-w-0 flex-1">
                          <p class="font-medium truncate">{rec.title}</p>
                          {#if rec.author}
                            <p class="text-xs text-muted-foreground truncate">{rec.author}</p>
                          {/if}
                          <div class="mt-1 flex flex-wrap gap-1">
                            {#each rec.reasons as reason}
                              <span class="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">{reason}</span>
                            {/each}
                          </div>
                        </div>
                        <span class="shrink-0 text-xs text-muted-foreground/60 tabular-nums">{rec.score}pt</span>
                      </a>
                    {/each}
                  </div>
                {/if}
              </div>
            {/if}
          </div>

          <!-- Marginalia -->
          <div class="mt-6">
            <Marginalia {bookId} esotericEnabled={book?.esoteric_enabled ?? false} />
          </div>

          <!-- AI Analysis -->
          <div class="mt-6">
            <BookAnalysis {bookId} {isAdmin} esotericEnabled={book?.esoteric_enabled ?? false} />
          </div>

          <!-- Literary / Poetic Analysis -->
          <div class="mt-6">
            <LiteraryAnalysis {bookId} />
          </div>

          <!-- Computational Esoteric Analysis -->
          {#if book?.esoteric_enabled}
            <div class="mt-6">
              <EsotericAnalysis {bookId} />
            </div>
          {:else if isAdmin}
            <div class="mt-6 rounded-lg border border-dashed px-4 py-3 text-center">
              <p class="text-sm text-muted-foreground">Esoteric analysis is disabled for this book.</p>
              <button
                class="mt-1 text-xs text-amber-600 hover:text-amber-700 underline"
                onclick={async () => {
                  if (!book) return;
                  await setEsotericEnabled(book.id, true);
                  book = { ...book, esoteric_enabled: true };
                }}
              >Enable esoteric analysis</button>
            </div>
          {/if}

          <!-- Disable esoteric (admin only, when enabled) -->
          {#if isAdmin && book?.esoteric_enabled}
            <div class="mt-2 text-right">
              <button
                class="text-xs text-muted-foreground/50 hover:text-muted-foreground underline"
                onclick={async () => {
                  if (!book) return;
                  await setEsotericEnabled(book.id, false);
                  book = { ...book, esoteric_enabled: false };
                }}
              >Disable esoteric analysis</button>
            </div>
          {/if}
        </div>
      </div>
    {/if}
  </div>
{:else}
  <div class="flex flex-col items-center justify-center py-16 text-muted-foreground">
    <BookOpen class="h-12 w-12" />
    <p class="mt-4">Book not found</p>
  </div>
{/if}
