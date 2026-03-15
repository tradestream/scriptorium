<script lang="ts">
  import { Button } from "$lib/components/ui/button";
  import { Input } from "$lib/components/ui/input";
  import { Separator } from "$lib/components/ui/separator";
  import { X, Plus, Save, Lock, Unlock } from "lucide-svelte";
  import * as api from "$lib/api/client";
  import type { Book, BookSeriesEntry } from "$lib/types/index";
  import { onMount, untrack } from "svelte";

  interface Props {
    book: Book;
    onSave?: (updated: Book) => void;
    onCancel?: () => void;
  }

  let { book, onSave, onCancel }: Props = $props();

  let title = $state(book.title);
  let subtitle = $state(book.subtitle ?? '');
  let description = $state(book.description ?? '');
  let isbn = $state(book.isbn ?? '');
  let language = $state(book.language ?? '');
  let published_date = $state(book.published_date ?? '');
  let publisher = $state(book.publisher ?? '');
  let authorNames = $state(untrack(() => book.authors.map(a => a.name)));
  let tagNames = $state(untrack(() => book.tags.map(t => t.name)));
  // seriesEntries holds name + position/volume/arc; loaded from API on mount
  type SeriesRow = { name: string; position: number | null; volume: string | null; arc: string | null; series_id?: number };
  let seriesEntries = $state<SeriesRow[]>(untrack(() => book.series.map(s => ({ name: s.name, position: null, volume: null, arc: null, series_id: s.id }))));

  onMount(async () => {
    if (book.series.length > 0) {
      try {
        const entries = await api.getBookSeriesEntries(book.id);
        seriesEntries = book.series.map(s => {
          const match = entries.find(e => e.series_id === s.id);
          return { name: s.name, series_id: s.id, position: match?.position ?? null, volume: match?.volume ?? null, arc: match?.arc ?? null };
        });
      } catch { /* non-critical — fall back to names only */ }
    }
  });
  let translatorNames = $state(untrack(() => [...(book.translators ?? [])]));
  let editorNames = $state(untrack(() => [...(book.editors ?? [])]));
  let illustratorNames = $state(untrack(() => [...(book.illustrators ?? [])]));
  let coloristNames = $state(untrack(() => [...(book.colorists ?? [])]));

  let authorInput = $state('');
  let tagInput = $state('');
  let seriesInput = $state('');
  let translatorInput = $state('');
  let editorInput = $state('');
  let illustratorInput = $state('');
  let coloristInput = $state('');
  let saving = $state(false);
  let error = $state('');

  // ── Field locking ─────────────────────────────────────────────────────────
  let lockedFields = $state<Set<string>>(untrack(() => new Set(book.locked_fields ?? [])));

  function isLocked(field: string): boolean {
    return lockedFields.has(field);
  }

  async function toggleLock(field: string) {
    const next = new Set(lockedFields);
    if (next.has(field)) {
      next.delete(field);
    } else {
      next.add(field);
    }
    lockedFields = next;
    try {
      await api.setLockedFields(book.id, [...next]);
    } catch { /* non-critical — UI reflects state, will retry on next save */ }
  }

  // ─────────────────────────────────────────────────────────────────────────

  function addAuthor() {
    const v = authorInput.trim();
    if (v && !authorNames.includes(v)) authorNames = [...authorNames, v];
    authorInput = '';
  }

  function removeAuthor(name: string) {
    authorNames = authorNames.filter(a => a !== name);
  }

  function addTag() {
    const v = tagInput.trim().toLowerCase();
    if (v && !tagNames.includes(v)) tagNames = [...tagNames, v];
    tagInput = '';
  }

  function removeTag(name: string) {
    tagNames = tagNames.filter(t => t !== name);
  }

  function addSeries() {
    const v = seriesInput.trim();
    if (v && !seriesEntries.some(e => e.name === v)) {
      seriesEntries = [...seriesEntries, { name: v, position: null, volume: null, arc: null }];
    }
    seriesInput = '';
  }

  function removeSeries(name: string) {
    seriesEntries = seriesEntries.filter(e => e.name !== name);
  }

  function addContributor(list: string[], input: string, setList: (v: string[]) => void, setInput: (v: string) => void) {
    const v = input.trim();
    if (v && !list.includes(v)) setList([...list, v]);
    setInput('');
  }

  function removeContributor(list: string[], name: string, setList: (v: string[]) => void) {
    setList(list.filter(n => n !== name));
  }

  async function save() {
    saving = true;
    error = '';
    try {
      const updated = await api.updateBook(book.id, {
        title: title.trim() || undefined,
        subtitle: subtitle.trim() || null,
        description: description.trim() || null,
        isbn: isbn.trim() || null,
        language: language.trim() || null,
        published_date: published_date.trim() || null,
        publisher: publisher.trim() || null,
        author_names: authorNames,
        tag_names: tagNames,
        series_names: seriesEntries.map(e => e.name),
        translator_names: translatorNames,
        editor_names: editorNames,
        illustrator_names: illustratorNames,
        colorist_names: coloristNames,
      });

      // After book update, save position/volume/arc for each series
      // updated.series has the authoritative IDs (including newly created ones)
      const hasEntryData = seriesEntries.some(e => e.position != null || e.volume || e.arc);
      if (hasEntryData && updated.series?.length) {
        await Promise.all(
          updated.series.map(s => {
            const row = seriesEntries.find(e => e.name === s.name);
            if (!row) return Promise.resolve();
            return api.updateSeriesEntries(s.id, [{
              book_id: book.id,
              position: row.position ?? null,
              volume: row.volume || null,
              arc: row.arc || null,
            }]);
          })
        );
      }

      onSave?.(updated);
    } catch (err) {
      error = err instanceof Error ? err.message : 'Save failed';
    } finally {
      saving = false;
    }
  }

  function handleKeydown(e: KeyboardEvent, fn: () => void) {
    if (e.key === 'Enter') { e.preventDefault(); fn(); }
  }
</script>

<div class="space-y-5">
  <div class="space-y-1.5">
    <div class="flex items-center justify-between">
      <label class="text-sm font-medium" for="edit-title">Title</label>
      <button onclick={() => toggleLock('title')} title={isLocked('title') ? 'Unlock title' : 'Lock title'} class="text-muted-foreground/40 hover:text-muted-foreground transition-colors">
        {#if isLocked('title')}<Lock class="h-3.5 w-3.5 text-amber-500" />{:else}<Unlock class="h-3.5 w-3.5" />{/if}
      </button>
    </div>
    <Input id="edit-title" bind:value={title} disabled={isLocked('title')} />
  </div>

  <div class="space-y-1.5">
    <label class="text-sm font-medium" for="edit-subtitle">Subtitle</label>
    <Input id="edit-subtitle" bind:value={subtitle} placeholder="Optional subtitle" />
  </div>

  <div class="space-y-1.5">
    <div class="flex items-center justify-between">
      <label class="text-sm font-medium" for="edit-desc">Description</label>
      <button onclick={() => toggleLock('description')} title={isLocked('description') ? 'Unlock description' : 'Lock description'} class="text-muted-foreground/40 hover:text-muted-foreground transition-colors">
        {#if isLocked('description')}<Lock class="h-3.5 w-3.5 text-amber-500" />{:else}<Unlock class="h-3.5 w-3.5" />{/if}
      </button>
    </div>
    <textarea
      id="edit-desc"
      bind:value={description}
      rows="4"
      disabled={isLocked('description')}
      class="w-full rounded-md border bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
    ></textarea>
  </div>

  <div class="grid grid-cols-2 gap-4">
    <div class="space-y-1.5">
      <div class="flex items-center justify-between">
        <label class="text-sm font-medium" for="edit-isbn">ISBN</label>
        <button onclick={() => toggleLock('isbn')} title={isLocked('isbn') ? 'Unlock' : 'Lock'} class="text-muted-foreground/40 hover:text-muted-foreground transition-colors">
          {#if isLocked('isbn')}<Lock class="h-3.5 w-3.5 text-amber-500" />{:else}<Unlock class="h-3.5 w-3.5" />{/if}
        </button>
      </div>
      <Input id="edit-isbn" bind:value={isbn} placeholder="978-..." disabled={isLocked('isbn')} />
    </div>
    <div class="space-y-1.5">
      <div class="flex items-center justify-between">
        <label class="text-sm font-medium" for="edit-lang">Language</label>
        <button onclick={() => toggleLock('language')} title={isLocked('language') ? 'Unlock' : 'Lock'} class="text-muted-foreground/40 hover:text-muted-foreground transition-colors">
          {#if isLocked('language')}<Lock class="h-3.5 w-3.5 text-amber-500" />{:else}<Unlock class="h-3.5 w-3.5" />{/if}
        </button>
      </div>
      <Input id="edit-lang" bind:value={language} placeholder="en" disabled={isLocked('language')} />
    </div>
    <div class="space-y-1.5">
      <div class="flex items-center justify-between">
        <label class="text-sm font-medium" for="edit-date">Published Date</label>
        <button onclick={() => toggleLock('published_date')} title={isLocked('published_date') ? 'Unlock' : 'Lock'} class="text-muted-foreground/40 hover:text-muted-foreground transition-colors">
          {#if isLocked('published_date')}<Lock class="h-3.5 w-3.5 text-amber-500" />{:else}<Unlock class="h-3.5 w-3.5" />{/if}
        </button>
      </div>
      <Input id="edit-date" bind:value={published_date} placeholder="2024-01-15" disabled={isLocked('published_date')} />
    </div>
    <div class="space-y-1.5">
      <div class="flex items-center justify-between">
        <label class="text-sm font-medium" for="edit-publisher">Publisher</label>
        <button onclick={() => toggleLock('publisher')} title={isLocked('publisher') ? 'Unlock' : 'Lock'} class="text-muted-foreground/40 hover:text-muted-foreground transition-colors">
          {#if isLocked('publisher')}<Lock class="h-3.5 w-3.5 text-amber-500" />{:else}<Unlock class="h-3.5 w-3.5" />{/if}
        </button>
      </div>
      <Input id="edit-publisher" bind:value={publisher} placeholder="Publisher name" disabled={isLocked('publisher')} />
    </div>
  </div>

  <Separator />

  <!-- Authors -->
  <div class="space-y-2">
    <div class="flex items-center justify-between">
      <p class="text-sm font-medium">Authors</p>
      <button onclick={() => toggleLock('authors')} title={isLocked('authors') ? 'Unlock authors' : 'Lock authors'} class="text-muted-foreground/40 hover:text-muted-foreground transition-colors">
        {#if isLocked('authors')}<Lock class="h-3.5 w-3.5 text-amber-500" />{:else}<Unlock class="h-3.5 w-3.5" />{/if}
      </button>
    </div>
    <div class="flex flex-wrap gap-1.5">
      {#each authorNames as name}
        <span class="flex items-center gap-1 rounded-full bg-secondary px-2.5 py-0.5 text-sm">
          {name}
          {#if !isLocked('authors')}
            <button onclick={() => removeAuthor(name)} class="text-muted-foreground hover:text-foreground">
              <X class="h-3 w-3" />
            </button>
          {/if}
        </span>
      {/each}
    </div>
    {#if !isLocked('authors')}
      <div class="flex gap-2">
        <Input bind:value={authorInput} placeholder="Add author..." onkeydown={(e) => handleKeydown(e, addAuthor)} class="flex-1" />
        <Button variant="outline" size="icon" onclick={addAuthor}><Plus class="h-4 w-4" /></Button>
      </div>
    {/if}
  </div>

  <!-- Tags -->
  <div class="space-y-2">
    <div class="flex items-center justify-between">
      <p class="text-sm font-medium">Tags</p>
      <button onclick={() => toggleLock('tags')} title={isLocked('tags') ? 'Unlock tags' : 'Lock tags'} class="text-muted-foreground/40 hover:text-muted-foreground transition-colors">
        {#if isLocked('tags')}<Lock class="h-3.5 w-3.5 text-amber-500" />{:else}<Unlock class="h-3.5 w-3.5" />{/if}
      </button>
    </div>
    <div class="flex flex-wrap gap-1.5">
      {#each tagNames as name}
        <span class="flex items-center gap-1 rounded-full bg-secondary px-2.5 py-0.5 text-sm">
          {name}
          {#if !isLocked('tags')}
            <button onclick={() => removeTag(name)} class="text-muted-foreground hover:text-foreground">
              <X class="h-3 w-3" />
            </button>
          {/if}
        </span>
      {/each}
    </div>
    {#if !isLocked('tags')}
      <div class="flex gap-2">
        <Input bind:value={tagInput} placeholder="Add tag..." onkeydown={(e) => handleKeydown(e, addTag)} class="flex-1" />
        <Button variant="outline" size="icon" onclick={addTag}><Plus class="h-4 w-4" /></Button>
      </div>
    {/if}
  </div>

  <!-- Series -->
  <div class="space-y-2">
    <div class="flex items-center justify-between">
      <p class="text-sm font-medium">Series</p>
      <button onclick={() => toggleLock('series')} title={isLocked('series') ? 'Unlock series' : 'Lock series'} class="text-muted-foreground/40 hover:text-muted-foreground transition-colors">
        {#if isLocked('series')}<Lock class="h-3.5 w-3.5 text-amber-500" />{:else}<Unlock class="h-3.5 w-3.5" />{/if}
      </button>
    </div>

    {#if seriesEntries.length > 0}
      <!-- Column headers -->
      <div class="grid grid-cols-[1fr_4rem_5rem_5rem_1.5rem] gap-1.5 px-0.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/50">
        <span>Name</span><span class="text-center">Pos.</span><span class="text-center">Volume</span><span class="text-center">Arc</span><span></span>
      </div>
      <div class="space-y-1">
        {#each seriesEntries as entry, i}
          <div class="grid grid-cols-[1fr_4rem_5rem_5rem_1.5rem] items-center gap-1.5">
            <span class="truncate rounded bg-secondary px-2 py-1 text-sm">{entry.name}</span>
            <input
              type="number"
              step="0.5"
              bind:value={entry.position}
              placeholder="—"
              disabled={isLocked('series')}
              class="rounded border bg-background px-1.5 py-1 text-center text-xs tabular-nums focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-50"
              title="Position in series"
            />
            <input
              type="text"
              bind:value={entry.volume}
              placeholder="—"
              disabled={isLocked('series')}
              class="rounded border bg-background px-1.5 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-50"
              title="Volume"
            />
            <input
              type="text"
              bind:value={entry.arc}
              placeholder="—"
              disabled={isLocked('series')}
              class="rounded border bg-background px-1.5 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-50"
              title="Arc / Story Arc"
            />
            {#if !isLocked('series')}
              <button onclick={() => removeSeries(entry.name)} class="flex items-center justify-center text-muted-foreground/40 hover:text-destructive transition-colors" title="Remove from series">
                <X class="h-3.5 w-3.5" />
              </button>
            {:else}
              <span></span>
            {/if}
          </div>
        {/each}
      </div>
    {/if}

    {#if !isLocked('series')}
      <div class="flex gap-2">
        <Input bind:value={seriesInput} placeholder="Add series..." onkeydown={(e) => handleKeydown(e, addSeries)} class="flex-1" />
        <Button variant="outline" size="icon" onclick={addSeries}><Plus class="h-4 w-4" /></Button>
      </div>
    {/if}
  </div>

  <Separator />

  <!-- Contributors -->
  {#each [
    { label: 'Translator(s)', names: translatorNames, input: translatorInput, setNames: (v: string[]) => { translatorNames = v; }, setInput: (v: string) => { translatorInput = v; }, placeholder: 'Add translator...' },
    { label: 'Editor(s)', names: editorNames, input: editorInput, setNames: (v: string[]) => { editorNames = v; }, setInput: (v: string) => { editorInput = v; }, placeholder: 'Add editor...' },
    { label: 'Illustrator(s)', names: illustratorNames, input: illustratorInput, setNames: (v: string[]) => { illustratorNames = v; }, setInput: (v: string) => { illustratorInput = v; }, placeholder: 'Add illustrator...' },
    { label: 'Colorist(s)', names: coloristNames, input: coloristInput, setNames: (v: string[]) => { coloristNames = v; }, setInput: (v: string) => { coloristInput = v; }, placeholder: 'Add colorist...' },
  ] as contrib}
    <div class="space-y-2">
      <p class="text-sm font-medium">{contrib.label}</p>
      <div class="flex flex-wrap gap-1.5">
        {#each contrib.names as name}
          <span class="flex items-center gap-1 rounded-full bg-secondary px-2.5 py-0.5 text-sm">
            {name}
            <button onclick={() => removeContributor(contrib.names, name, contrib.setNames)} class="text-muted-foreground hover:text-foreground">
              <X class="h-3 w-3" />
            </button>
          </span>
        {/each}
      </div>
      <div class="flex gap-2">
        <Input
          value={contrib.input}
          placeholder={contrib.placeholder}
          onkeydown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addContributor(contrib.names, contrib.input, contrib.setNames, contrib.setInput); } }}
          oninput={(e) => contrib.setInput((e.target as HTMLInputElement).value)}
          class="flex-1"
        />
        <Button variant="outline" size="icon" onclick={() => addContributor(contrib.names, contrib.input, contrib.setNames, contrib.setInput)}><Plus class="h-4 w-4" /></Button>
      </div>
    </div>
  {/each}

  {#if error}
    <p class="text-sm text-destructive">{error}</p>
  {/if}

  <div class="flex justify-end gap-2 pt-2">
    <Button variant="outline" onclick={onCancel} disabled={saving}>Cancel</Button>
    <Button onclick={save} disabled={saving}>
      <Save class="mr-2 h-4 w-4" />
      {saving ? 'Saving...' : 'Save Changes'}
    </Button>
  </div>
</div>
