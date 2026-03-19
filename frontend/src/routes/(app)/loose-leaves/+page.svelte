<script lang="ts">
  import { Inbox, Loader2, ChevronDown, ChevronUp, Check, X, RefreshCw, BookOpen, Tag, Upload } from 'lucide-svelte';
  import * as api from '$lib/api/client';
  import type { DropItem, DropPreview } from '$lib/api/client';

  let items = $state<DropItem[]>([]);
  let loading = $state(true);
  let libraries = $state<{ id: number; name: string }[]>([]);

  // Upload state
  let dragOver = $state(false);
  let uploading = $state(false);
  let uploadError = $state('');
  let fileInput: HTMLInputElement;

  const ACCEPTED_FORMATS = '.epub,.pdf,.cbz,.cbr,.cbr,.mobi,.fb2,.djvu';

  async function handleUpload(files: FileList | File[]) {
    const fileArr = Array.from(files).filter(f => /\.(epub|pdf|cbz|cbr|mobi|fb2|djvu)$/i.test(f.name));
    if (!fileArr.length) {
      uploadError = 'No supported book files found (epub, pdf, cbz, cbr, mobi, fb2, djvu)';
      return;
    }
    uploading = true;
    uploadError = '';
    try {
      const newItems = await api.uploadToLooseLeaves(fileArr);
      // Add to queue with default library selection
      for (const item of newItems) {
        if (!selectedLibrary[item.filename] && libraries.length > 0) {
          selectedLibrary[item.filename] = libraries[0].id;
        }
      }
      items = [...items, ...newItems];
    } catch (e) {
      uploadError = e instanceof Error ? e.message : 'Upload failed';
    } finally {
      uploading = false;
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    dragOver = false;
    if (e.dataTransfer?.files) handleUpload(e.dataTransfer.files);
  }

  // Per-file UI state
  let previewing = $state<Record<string, boolean>>({});
  let previews = $state<Record<string, DropPreview>>({});
  let loadingPreview = $state<Record<string, boolean>>({});
  let selectedLibrary = $state<Record<string, number>>({});
  let importing = $state<Record<string, boolean>>({});
  let rejecting = $state<Record<string, boolean>>({});
  let messages = $state<Record<string, { text: string; ok: boolean }>>({});

  async function load() {
    loading = true;
    try {
      const [dropped, libs] = await Promise.all([
        api.getLooseLeavesPending(),
        fetch('/api/v1/libraries', {
          headers: { Authorization: `Bearer ${api.getAuthToken()}` },
        }).then(r => r.ok ? r.json() : []),
      ]);
      items = dropped;
      libraries = Array.isArray(libs) ? libs : (libs.items ?? []);
      // Default library selection
      if (libraries.length > 0) {
        for (const item of items) {
          if (!selectedLibrary[item.filename]) {
            selectedLibrary[item.filename] = libraries[0].id;
          }
        }
      }
    } catch (e) {
      console.error(e);
    } finally {
      loading = false;
    }
  }

  async function togglePreview(item: DropItem) {
    const fn = item.filename;
    if (previewing[fn]) {
      previewing = { ...previewing, [fn]: false };
      return;
    }
    previewing = { ...previewing, [fn]: true };
    if (!previews[fn]) {
      loadingPreview = { ...loadingPreview, [fn]: true };
      try {
        previews = { ...previews, [fn]: await api.previewLooseLeaf(fn) };
      } catch { /* non-critical */ } finally {
        loadingPreview = { ...loadingPreview, [fn]: false };
      }
    }
  }

  async function importItem(item: DropItem) {
    const fn = item.filename;
    const libId = selectedLibrary[fn];
    if (!libId) return;
    importing = { ...importing, [fn]: true };
    try {
      const result = await api.importFromLooseLeaves(fn, libId);
      messages = { ...messages, [fn]: { text: result.message, ok: result.status !== 'error' } };
      if (result.status !== 'error') {
        items = items.filter(i => i.filename !== fn);
      }
    } catch (e) {
      messages = { ...messages, [fn]: { text: e instanceof Error ? e.message : 'Import failed', ok: false } };
    } finally {
      importing = { ...importing, [fn]: false };
    }
  }

  async function rejectItem(item: DropItem) {
    const fn = item.filename;
    if (!confirm(`Reject and delete "${fn}"?`)) return;
    rejecting = { ...rejecting, [fn]: true };
    try {
      await api.rejectFromLooseLeaves(fn);
      items = items.filter(i => i.filename !== fn);
    } catch (e) {
      messages = { ...messages, [fn]: { text: e instanceof Error ? e.message : 'Reject failed', ok: false } };
    } finally {
      rejecting = { ...rejecting, [fn]: false };
    }
  }

  function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }

  // Global default library + bulk actions
  let defaultLibraryId = $state<number | null>(null);
  let selected = $state<Set<string>>(new Set());
  let bulkImporting = $state(false);
  let bulkMsg = $state('');

  function toggleSelect(fn: string) {
    const next = new Set(selected);
    if (next.has(fn)) next.delete(fn); else next.add(fn);
    selected = next;
  }

  function selectAll() {
    selected = new Set(items.map(i => i.filename));
  }

  function selectNone() {
    selected = new Set();
  }

  function applyDefaultToAll() {
    if (!defaultLibraryId) return;
    const updated = { ...selectedLibrary };
    for (const item of items) {
      if (selected.size === 0 || selected.has(item.filename)) {
        updated[item.filename] = defaultLibraryId;
      }
    }
    selectedLibrary = updated;
  }

  async function importAll() {
    const toImport = items.filter(i => selected.size === 0 || selected.has(i.filename));
    if (toImport.length === 0) return;
    if (!confirm(`Import ${toImport.length} file${toImport.length > 1 ? 's' : ''}?`)) return;
    bulkImporting = true;
    bulkMsg = '';
    try {
      const files = toImport.map(i => ({
        filename: i.filename,
        library_id: selectedLibrary[i.filename] || null,
      }));
      const defLib = defaultLibraryId || (libraries.length > 0 ? libraries[0].id : 0);
      const result = await api.bulkImportFromLooseLeaves(files, defLib);
      bulkMsg = `Imported ${result.imported} of ${result.total} files`;
      // Remove imported items from the list
      const importedFilenames = new Set(result.results.filter(r => r.status === 'imported').map(r => r.filename));
      items = items.filter(i => !importedFilenames.has(i.filename));
      selected = new Set();
    } catch (e) {
      bulkMsg = e instanceof Error ? e.message : 'Bulk import failed';
    } finally {
      bulkImporting = false;
    }
  }

  $effect(() => { load(); });
  $effect(() => {
    if (libraries.length > 0 && !defaultLibraryId) {
      // Default to "Books" library if it exists, otherwise first
      const booksLib = libraries.find(l => l.name.toLowerCase() === 'books');
      defaultLibraryId = booksLib?.id ?? libraries[0].id;
    }
  });
</script>

<div class="mx-auto max-w-3xl space-y-6 p-6">
  <div class="flex items-center gap-3">
    <Inbox class="h-6 w-6 text-primary" />
    <div>
      <h1 class="text-2xl font-semibold">Loose Leaves</h1>
      <p class="text-sm text-muted-foreground">Review dropped files before importing to your library</p>
    </div>
    <button
      class="ml-auto flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm transition-colors hover:bg-accent"
      onclick={load}
    >
      <RefreshCw class="h-3.5 w-3.5" /> Refresh
    </button>
  </div>

  <!-- Upload zone -->
  <div
    role="region"
    aria-label="Upload drop zone"
    class="relative rounded-lg border-2 border-dashed transition-colors {dragOver ? 'border-primary bg-primary/5' : 'border-border hover:border-border/80'}"
    ondragover={(e) => { e.preventDefault(); dragOver = true; }}
    ondragleave={() => { dragOver = false; }}
    ondrop={onDrop}
  >
    <input
      bind:this={fileInput}
      type="file"
      accept={ACCEPTED_FORMATS}
      multiple
      class="hidden"
      onchange={(e) => { if (e.currentTarget.files) handleUpload(e.currentTarget.files); e.currentTarget.value = ''; }}
    />
    <button
      class="flex w-full flex-col items-center gap-2 py-8 text-center"
      onclick={() => fileInput.click()}
      disabled={uploading}
    >
      {#if uploading}
        <Loader2 class="h-8 w-8 animate-spin text-primary" />
        <p class="text-sm font-medium text-primary">Uploading…</p>
      {:else}
        <Upload class="h-8 w-8 text-muted-foreground/50" />
        <p class="text-sm font-medium text-foreground">Drop book files here or click to upload</p>
        <p class="text-xs text-muted-foreground">EPUB · PDF · CBZ · CBR · MOBI · FB2 · DJVU</p>
      {/if}
    </button>
    {#if uploadError}
      <p class="border-t px-4 py-2 text-xs text-destructive">{uploadError}</p>
    {/if}
  </div>

  {#if loading}
    <div class="flex justify-center py-16">
      <Loader2 class="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  {:else if items.length === 0}
    <div class="py-16 text-center text-muted-foreground">
      <Inbox class="mx-auto mb-3 h-10 w-10 opacity-20" />
      <p class="text-sm">No files pending review.</p>
      <p class="mt-1 text-xs text-muted-foreground/60">
        Drop book files into the <code class="rounded bg-muted px-1">LOOSE_LEAVES_PATH</code> folder to see them here.
      </p>
    </div>
  {:else}
    <!-- Global controls bar -->
    <div class="flex flex-wrap items-center gap-3 rounded-lg border bg-muted/30 p-3">
      <div class="flex items-center gap-2 text-xs">
        <button onclick={selected.size === items.length ? selectNone : selectAll}
          class="rounded border px-2 py-1 hover:bg-accent transition-colors">
          {selected.size === items.length ? 'Deselect all' : 'Select all'}
        </button>
        <span class="text-muted-foreground">{selected.size > 0 ? `${selected.size} selected` : `${items.length} files`}</span>
      </div>
      <div class="flex items-center gap-2 ml-auto">
        <label class="text-xs text-muted-foreground shrink-0">Default library:</label>
        <select bind:value={defaultLibraryId}
          class="h-7 rounded border bg-background px-2 text-xs outline-none focus:ring-1 focus:ring-ring">
          {#each libraries as lib}
            <option value={lib.id}>{lib.name}</option>
          {/each}
        </select>
        <button onclick={applyDefaultToAll}
          class="rounded border px-2 py-1 text-xs hover:bg-accent transition-colors"
          title="Apply default library to all{selected.size > 0 ? ' selected' : ''} files">
          Apply to {selected.size > 0 ? 'selected' : 'all'}
        </button>
        <button onclick={importAll}
          disabled={bulkImporting}
          class="rounded bg-primary px-3 py-1 text-xs text-primary-foreground disabled:opacity-50 transition-opacity">
          {bulkImporting ? 'Importing…' : `Import ${selected.size > 0 ? selected.size : 'all'}`}
        </button>
      </div>
    </div>
    {#if bulkMsg}
      <p class="text-sm text-muted-foreground">{bulkMsg}</p>
    {/if}

    <div class="space-y-3">
      {#each items as item (item.filename)}
        {@const fn = item.filename}
        {@const isOpen = previewing[fn] ?? false}
        {@const preview = previews[fn]}
        {@const msg = messages[fn]}
        <div class="rounded-lg border">
          <!-- Header row -->
          <div class="flex items-center gap-3 p-4">
            <input
              type="checkbox"
              checked={selected.has(fn)}
              onchange={() => toggleSelect(fn)}
              class="h-4 w-4 rounded border accent-primary shrink-0"
            />
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <span class="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase text-muted-foreground shrink-0">{item.format}</span>
                <p class="font-medium truncate text-sm">{item.guessed_title}</p>
              </div>
              <p class="mt-0.5 text-[11px] text-muted-foreground truncate">{fn} · {formatSize(item.size_bytes)}</p>
              {#if msg}
                <p class="mt-1 text-xs {msg.ok ? 'text-green-600' : 'text-destructive'}">{msg.text}</p>
              {/if}
            </div>

            <!-- Library selector -->
            {#if libraries.length > 0}
              <select
                bind:value={selectedLibrary[fn]}
                class="h-8 rounded border bg-background px-2 text-xs outline-none focus:ring-1 focus:ring-ring shrink-0"
              >
                {#each libraries as lib}
                  <option value={lib.id}>{lib.name}</option>
                {/each}
              </select>
            {/if}

            <!-- Actions -->
            <div class="flex items-center gap-1.5 shrink-0">
              <button
                onclick={() => togglePreview(item)}
                class="flex items-center gap-1 rounded-md border px-2.5 py-1.5 text-xs transition-colors hover:bg-accent"
                title="Preview metadata"
              >
                {#if isOpen}<ChevronUp class="h-3 w-3" />{:else}<ChevronDown class="h-3 w-3" />{/if}
                Preview
              </button>
              <button
                onclick={() => importItem(item)}
                disabled={importing[fn] || !selectedLibrary[fn]}
                class="flex items-center gap-1 rounded-md bg-primary px-2.5 py-1.5 text-xs text-primary-foreground disabled:opacity-50 transition-opacity"
                title="Import to library"
              >
                <Check class="h-3 w-3" />
                {importing[fn] ? 'Importing…' : 'Import'}
              </button>
              <button
                onclick={() => rejectItem(item)}
                disabled={rejecting[fn]}
                class="flex items-center gap-1 rounded-md border border-destructive/30 px-2.5 py-1.5 text-xs text-destructive hover:bg-destructive/10 disabled:opacity-50 transition-colors"
                title="Reject and delete"
              >
                <X class="h-3 w-3" />
              </button>
            </div>
          </div>

          <!-- Preview panel -->
          {#if isOpen}
            <div class="border-t bg-muted/20 p-4 space-y-3 text-sm">
              {#if loadingPreview[fn]}
                <div class="flex justify-center py-4">
                  <Loader2 class="h-4 w-4 animate-spin text-muted-foreground" />
                </div>
              {:else if preview}
                <div class="grid grid-cols-2 gap-3 sm:grid-cols-3">
                  {#if preview.title}
                    <div class="sm:col-span-2">
                      <p class="text-xs text-muted-foreground">Title</p>
                      <p class="font-medium">{preview.title}</p>
                    </div>
                  {/if}
                  {#if preview.authors?.length}
                    <div>
                      <p class="text-xs text-muted-foreground">Author(s)</p>
                      <p>{preview.authors.join(', ')}</p>
                    </div>
                  {/if}
                  {#if preview.published_date}
                    <div>
                      <p class="text-xs text-muted-foreground">Published</p>
                      <p>{preview.published_date}</p>
                    </div>
                  {/if}
                  {#if preview.language}
                    <div>
                      <p class="text-xs text-muted-foreground">Language</p>
                      <p class="uppercase">{preview.language}</p>
                    </div>
                  {/if}
                  {#if preview.isbn}
                    <div>
                      <p class="text-xs text-muted-foreground">ISBN</p>
                      <p class="font-mono text-xs">{preview.isbn}</p>
                    </div>
                  {/if}
                </div>
                {#if preview.description}
                  <p class="text-xs text-muted-foreground leading-relaxed line-clamp-3">{preview.description}</p>
                {/if}
                {#if preview.tags?.length}
                  <div class="flex flex-wrap gap-1">
                    {#each preview.tags.slice(0, 8) as tag}
                      <span class="flex items-center gap-0.5 rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                        <Tag class="h-2.5 w-2.5" />{tag}
                      </span>
                    {/each}
                  </div>
                {/if}
                {#if preview.cover_url}
                  <div class="flex items-start gap-3">
                    <img
                      src={preview.cover_url}
                      alt="Cover preview"
                      class="h-24 w-auto rounded shadow-sm object-cover"
                    />
                  </div>
                {/if}
              {:else}
                <p class="text-xs text-muted-foreground text-center py-2">
                  No metadata found. The book will be imported with filename-derived title.
                </p>
              {/if}
            </div>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>
