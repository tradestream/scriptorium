<script lang="ts">
  import { goto } from '$app/navigation';
  import { BookPlus, Search, Loader2, X, BookOpen, Package } from 'lucide-svelte';
  import * as api from '$lib/api/client';

  let libraries = $state<{ id: number; name: string }[]>([]);

  // Step 1: lookup
  let lookupTitle = $state('');
  let lookupAuthor = $state('');
  let lookupISBN = $state('');
  let lookingUp = $state(false);

  // Step 2: form fields (pre-filled from lookup)
  let title = $state('');
  let subtitle = $state('');
  let authorInput = $state(''); // comma-separated
  let tagsInput = $state('');   // comma-separated
  let description = $state('');
  let isbn = $state('');
  let publisher = $state('');
  let publishedDate = $state('');
  let language = $state('');
  let libraryId = $state<number | null>(null);
  let physicalCopy = $state(false);
  let lookedUp = $state(false);
  let coverPreview = $state<string | null>(null);

  let saving = $state(false);
  let error = $state('');

  async function loadLibraries() {
    try {
      const r = await fetch('/api/v1/libraries', {
        headers: { Authorization: `Bearer ${api.getAuthToken()}` },
      });
      if (r.ok) {
        const data = await r.json();
        libraries = Array.isArray(data) ? data : (data.items ?? []);
        if (libraries.length > 0 && !libraryId) {
          libraryId = libraries[0].id;
        }
      }
    } catch { /* non-critical */ }
  }

  async function lookup() {
    if (!lookupTitle && !lookupISBN) return;
    lookingUp = true;
    error = '';
    try {
      const result = await api.lookupBookMetadata({
        title: lookupTitle || undefined,
        author: lookupAuthor || undefined,
        isbn: lookupISBN || undefined,
      });
      if (result && typeof result === 'object' && Object.keys(result).length > 0) {
        title = (result.title as string) ?? lookupTitle;
        authorInput = ((result.authors as string[]) ?? []).join(', ');
        tagsInput = ((result.tags as string[]) ?? []).join(', ');
        description = (result.description as string) ?? '';
        isbn = (result.isbn as string) ?? lookupISBN;
        publisher = (result.publisher as string) ?? '';
        language = (result.language as string) ?? '';
        if (result.published_date) {
          publishedDate = String(result.published_date).slice(0, 10);
        }
        coverPreview = (result.cover_url as string) ?? null;
      } else {
        title = lookupTitle;
        authorInput = lookupAuthor;
        isbn = lookupISBN;
      }
    } catch (e) {
      error = e instanceof Error ? e.message : 'Lookup failed';
      title = lookupTitle;
      authorInput = lookupAuthor;
      isbn = lookupISBN;
    } finally {
      lookingUp = false;
      lookedUp = true;
    }
  }

  function skipLookup() {
    title = lookupTitle;
    authorInput = lookupAuthor;
    isbn = lookupISBN;
    lookedUp = true;
  }

  async function save() {
    if (!title.trim() || !libraryId) return;
    saving = true;
    error = '';
    try {
      const book = await api.createBook({
        title: title.trim(),
        subtitle: subtitle.trim() || null,
        description: description.trim() || null,
        isbn: isbn.trim() || null,
        publisher: publisher.trim() || null,
        language: language.trim() || null,
        published_date: publishedDate || null,
        library_id: libraryId,
        physical_copy: physicalCopy,
        author_names: authorInput.split(',').map(s => s.trim()).filter(Boolean),
        tag_names: tagsInput.split(',').map(s => s.trim().toLowerCase()).filter(Boolean),
      });
      goto(`/book/${book.id}`);
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to create book';
    } finally {
      saving = false;
    }
  }

  $effect(() => { loadLibraries(); });
</script>

<div class="mx-auto max-w-2xl space-y-6 p-6">
  <div class="flex items-center gap-3">
    <BookPlus class="h-6 w-6 text-primary" />
    <div>
      <h1 class="text-2xl font-semibold">Add Book</h1>
      <p class="text-sm text-muted-foreground">Add a physical book, one you've read, or any title you want to track</p>
    </div>
  </div>

  {#if !lookedUp}
    <!-- Step 1: Lookup -->
    <div class="rounded-lg border p-5 space-y-4">
      <p class="text-sm font-medium">Look up metadata <span class="text-muted-foreground font-normal">(optional)</span></p>
      <div class="space-y-3">
        <input
          type="text"
          placeholder="Title"
          bind:value={lookupTitle}
          class="w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-ring"
          onkeydown={(e) => { if (e.key === 'Enter') lookup(); }}
        />
        <div class="grid grid-cols-2 gap-3">
          <input
            type="text"
            placeholder="Author (optional)"
            bind:value={lookupAuthor}
            class="rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-ring"
          />
          <input
            type="text"
            placeholder="ISBN (optional)"
            bind:value={lookupISBN}
            class="rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
      </div>
      <div class="flex gap-2">
        <button
          onclick={lookup}
          disabled={lookingUp || (!lookupTitle && !lookupISBN)}
          class="flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground disabled:opacity-50 transition-opacity"
        >
          {#if lookingUp}
            <Loader2 class="h-3.5 w-3.5 animate-spin" />
          {:else}
            <Search class="h-3.5 w-3.5" />
          {/if}
          {lookingUp ? 'Looking up…' : 'Look up'}
        </button>
        <button
          onclick={skipLookup}
          class="rounded-md border px-4 py-2 text-sm transition-colors hover:bg-accent"
        >
          Skip — enter manually
        </button>
      </div>
      {#if error}
        <p class="text-sm text-destructive">{error}</p>
      {/if}
    </div>
  {:else}
    <!-- Step 2: Form -->
    <div class="rounded-lg border p-5 space-y-4">
      <div class="flex items-start justify-between">
        <p class="text-sm font-medium">Book details</p>
        <button
          onclick={() => { lookedUp = false; error = ''; }}
          class="text-xs text-muted-foreground hover:text-foreground transition-colors"
        >← Back to search</button>
      </div>

      {#if error}
        <p class="text-sm text-destructive">{error}</p>
      {/if}

      <div class="flex gap-4">
        {#if coverPreview}
          <div class="shrink-0">
            <img src={coverPreview} alt="Cover" class="h-28 w-auto rounded shadow object-cover" />
            <button onclick={() => coverPreview = null} class="mt-1 block w-full text-center text-[10px] text-muted-foreground/50 hover:text-muted-foreground">remove</button>
          </div>
        {/if}
        <div class="flex-1 space-y-3 min-w-0">
          <div>
            <label class="text-xs text-muted-foreground">Title *</label>
            <input
              type="text"
              bind:value={title}
              class="mt-0.5 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-ring"
              placeholder="Required"
            />
          </div>
          <div>
            <label class="text-xs text-muted-foreground">Subtitle</label>
            <input
              type="text"
              bind:value={subtitle}
              class="mt-0.5 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
          <div>
            <label class="text-xs text-muted-foreground">Author(s) <span class="text-muted-foreground/60">comma-separated</span></label>
            <input
              type="text"
              bind:value={authorInput}
              placeholder="e.g. Cormac McCarthy, Homer"
              class="mt-0.5 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
        </div>
      </div>

      <div>
        <label class="text-xs text-muted-foreground">Description</label>
        <textarea
          bind:value={description}
          rows="3"
          class="mt-0.5 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-ring resize-none"
        ></textarea>
      </div>

      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="text-xs text-muted-foreground">ISBN</label>
          <input type="text" bind:value={isbn}
            class="mt-0.5 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-ring" />
        </div>
        <div>
          <label class="text-xs text-muted-foreground">Publisher</label>
          <input type="text" bind:value={publisher}
            class="mt-0.5 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-ring" />
        </div>
        <div>
          <label class="text-xs text-muted-foreground">Published date</label>
          <input type="date" bind:value={publishedDate}
            class="mt-0.5 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-ring" />
        </div>
        <div>
          <label class="text-xs text-muted-foreground">Language</label>
          <input type="text" bind:value={language} placeholder="en"
            class="mt-0.5 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-ring" />
        </div>
      </div>

      <div>
        <label class="text-xs text-muted-foreground">Tags <span class="text-muted-foreground/60">comma-separated</span></label>
        <input type="text" bind:value={tagsInput} placeholder="e.g. fiction, philosophy, western"
          class="mt-0.5 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-ring" />
      </div>

      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="text-xs text-muted-foreground">Library *</label>
          <select bind:value={libraryId}
            class="mt-0.5 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-ring">
            {#each libraries as lib}
              <option value={lib.id}>{lib.name}</option>
            {/each}
          </select>
        </div>
      </div>

      <!-- Ownership -->
      <div class="space-y-2 rounded-md border bg-muted/20 p-3">
        <p class="text-xs font-medium text-muted-foreground uppercase tracking-wide">Copy ownership</p>
        <label class="flex items-center gap-2.5 cursor-pointer">
          <input type="checkbox" bind:checked={physicalCopy}
            class="h-4 w-4 rounded border accent-primary" />
          <div>
            <span class="text-sm font-medium flex items-center gap-1.5">
              <Package class="h-3.5 w-3.5 text-amber-600" /> Physical copy
            </span>
            <p class="text-xs text-muted-foreground">I own a physical edition of this book</p>
          </div>
        </label>
        {#if !physicalCopy}
          <p class="text-xs text-muted-foreground pl-6">
            No copy selected — use this to track books you've read or want to read without owning a digital or physical copy.
          </p>
        {/if}
      </div>

      <div class="flex gap-2 pt-2">
        <button
          onclick={save}
          disabled={saving || !title.trim() || !libraryId}
          class="flex items-center gap-1.5 rounded-md bg-primary px-5 py-2 text-sm text-primary-foreground disabled:opacity-50 transition-opacity"
        >
          {#if saving}
            <Loader2 class="h-3.5 w-3.5 animate-spin" />
          {:else}
            <BookPlus class="h-3.5 w-3.5" />
          {/if}
          {saving ? 'Saving…' : 'Add book'}
        </button>
        <a href="/" class="rounded-md border px-5 py-2 text-sm transition-colors hover:bg-accent">
          Cancel
        </a>
      </div>
    </div>
  {/if}
</div>
