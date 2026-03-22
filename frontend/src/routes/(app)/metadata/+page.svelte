<script lang="ts">
  import { Input } from '$lib/components/ui/input';
  import { Button } from '$lib/components/ui/button';
  import { Badge } from '$lib/components/ui/badge';
  import { Pencil, GitMerge, Trash2, Check, X, BookOpen } from 'lucide-svelte';
  import * as api from '$lib/api/client';
  import type { AuthorDetail, TagDetail, SeriesDetail } from '$lib/types/index';
  import type { FieldValueDetail } from '$lib/api/client';
  import { onMount } from 'svelte';

  interface Props {
    data: { authors: AuthorDetail[]; tags: TagDetail[]; series: SeriesDetail[] };
  }
  let { data }: Props = $props();

  type Tab = 'authors' | 'tags' | 'series' | 'publishers' | 'languages';
  let activeTab = $state<Tab>('authors');

  let authors = $state<AuthorDetail[]>(data.authors);
  let tags = $state<TagDetail[]>(data.tags);
  let series = $state<SeriesDetail[]>(data.series);
  let publishers = $state<FieldValueDetail[]>([]);
  let languages = $state<FieldValueDetail[]>([]);
  let loadingField = $state(false);

  let filterText = $state('');

  // Load publishers/languages on first tab switch
  async function loadFieldValues(tab: 'publishers' | 'languages') {
    if (tab === 'publishers' && publishers.length > 0) return;
    if (tab === 'languages' && languages.length > 0) return;
    loadingField = true;
    try {
      if (tab === 'publishers') publishers = await api.getPublishers();
      else languages = await api.getLanguages();
    } catch { /* ignore */ }
    loadingField = false;
  }

  let filteredAuthors = $derived(
    filterText ? authors.filter(a => a.name.toLowerCase().includes(filterText.toLowerCase())) : authors
  );
  let filteredTags = $derived(
    filterText ? tags.filter(t => t.name.toLowerCase().includes(filterText.toLowerCase())) : tags
  );
  let filteredSeries = $derived(
    filterText ? series.filter(s => s.name.toLowerCase().includes(filterText.toLowerCase())) : series
  );
  let filteredPublishers = $derived(
    filterText ? publishers.filter(p => p.value.toLowerCase().includes(filterText.toLowerCase())) : publishers
  );
  let filteredLanguages = $derived(
    filterText ? languages.filter(l => l.value.toLowerCase().includes(filterText.toLowerCase())) : languages
  );

  // ID-based editing (authors/tags/series)
  let editingId = $state<number | null>(null);
  let editingName = $state('');
  let renameError = $state('');

  let mergeSourceId = $state<number | null>(null);
  let mergePending = $state(false);
  let mergeError = $state('');
  let globalError = $state('');

  // String-based editing (publishers/languages)
  let editingValue = $state<string | null>(null);
  let editingNewValue = $state('');
  let mergeSourceValue = $state<string | null>(null);

  const isFieldTab = $derived(activeTab === 'publishers' || activeTab === 'languages');

  function switchTab(tab: Tab) {
    activeTab = tab;
    editingId = null; editingName = ''; renameError = '';
    mergeSourceId = null; mergeError = '';
    editingValue = null; editingNewValue = '';
    mergeSourceValue = null;
    filterText = '';
    if (tab === 'publishers' || tab === 'languages') loadFieldValues(tab);
  }

  // ID-based operations
  function startEdit(id: number, name: string) {
    editingId = id; editingName = name; renameError = '';
  }
  function cancelEdit() { editingId = null; editingName = ''; renameError = ''; editingValue = null; editingNewValue = ''; }

  async function commitRename() {
    if (!editingId || !editingName.trim()) return;
    renameError = '';
    try {
      if (activeTab === 'authors') {
        const u = await api.renameAuthor(editingId, editingName.trim());
        authors = authors.map(a => a.id === editingId ? { ...a, name: u.name } : a);
      } else if (activeTab === 'tags') {
        const u = await api.renameTag(editingId, editingName.trim());
        tags = tags.map(t => t.id === editingId ? { ...t, name: u.name } : t);
      } else {
        const u = await api.renameSeriesEntity(editingId, editingName.trim());
        series = series.map(s => s.id === editingId ? { ...s, name: u.name } : s);
      }
      cancelEdit();
    } catch (err) {
      renameError = err instanceof Error ? err.message : 'Rename failed';
    }
  }

  function startMerge(id: number) { mergeSourceId = id; mergeError = ''; }
  function cancelMerge() { mergeSourceId = null; mergeError = ''; mergeSourceValue = null; }

  async function mergeInto(targetId: number) {
    if (!mergeSourceId || mergeSourceId === targetId || mergePending) return;
    mergePending = true; mergeError = '';
    try {
      if (activeTab === 'authors') {
        const u = await api.mergeAuthors(targetId, [mergeSourceId]);
        authors = authors.filter(a => a.id !== mergeSourceId).map(a => a.id === targetId ? { ...a, book_count: u.book_count } : a);
      } else if (activeTab === 'tags') {
        const u = await api.mergeTags(targetId, [mergeSourceId]);
        tags = tags.filter(t => t.id !== mergeSourceId).map(t => t.id === targetId ? { ...t, book_count: u.book_count } : t);
      } else {
        const u = await api.mergeSeriesEntities(targetId, [mergeSourceId]);
        series = series.filter(s => s.id !== mergeSourceId).map(s => s.id === targetId ? { ...s, book_count: u.book_count } : s);
      }
      mergeSourceId = null;
    } catch (err) {
      mergeError = err instanceof Error ? err.message : 'Merge failed';
    } finally {
      mergePending = false;
    }
  }

  async function deleteEntity(id: number) {
    if (!confirm('Delete this unused entry? This cannot be undone.')) return;
    try {
      if (activeTab === 'authors') {
        await api.deleteAuthorEntity(id); authors = authors.filter(a => a.id !== id);
      } else if (activeTab === 'tags') {
        await api.deleteTagEntity(id); tags = tags.filter(t => t.id !== id);
      } else {
        await api.deleteSeriesEntity(id); series = series.filter(s => s.id !== id);
      }
    } catch (err) {
      globalError = err instanceof Error ? err.message : 'Delete failed';
      setTimeout(() => { globalError = ''; }, 4000);
    }
  }

  // String-based operations (publishers/languages)
  function startFieldEdit(value: string) {
    editingValue = value; editingNewValue = value; renameError = '';
  }

  async function commitFieldRename() {
    if (!editingValue || !editingNewValue.trim()) return;
    renameError = '';
    try {
      if (activeTab === 'publishers') {
        const u = await api.renamePublisher(editingValue, editingNewValue.trim());
        publishers = publishers.filter(p => p.value !== editingValue).map(p => p.value === editingNewValue.trim() ? u : p);
        if (!publishers.some(p => p.value === u.value)) publishers = [u, ...publishers];
        // Deduplicate in case rename target existed
        const seen = new Set<string>();
        publishers = publishers.filter(p => { if (seen.has(p.value)) return false; seen.add(p.value); return true; });
      } else {
        const u = await api.renameLanguage(editingValue, editingNewValue.trim());
        languages = languages.filter(l => l.value !== editingValue).map(l => l.value === editingNewValue.trim() ? u : l);
        if (!languages.some(l => l.value === u.value)) languages = [u, ...languages];
        const seen = new Set<string>();
        languages = languages.filter(l => { if (seen.has(l.value)) return false; seen.add(l.value); return true; });
      }
      cancelEdit();
    } catch (err) {
      renameError = err instanceof Error ? err.message : 'Rename failed';
    }
  }

  function startFieldMerge(value: string) { mergeSourceValue = value; mergeError = ''; }

  async function mergeFieldInto(targetValue: string) {
    if (!mergeSourceValue || mergeSourceValue === targetValue || mergePending) return;
    mergePending = true; mergeError = '';
    try {
      if (activeTab === 'publishers') {
        const u = await api.mergePublishers([mergeSourceValue], targetValue);
        publishers = publishers.filter(p => p.value !== mergeSourceValue).map(p => p.value === targetValue ? u : p);
      } else {
        const u = await api.mergeLanguages([mergeSourceValue], targetValue);
        languages = languages.filter(l => l.value !== mergeSourceValue).map(l => l.value === targetValue ? u : l);
      }
      mergeSourceValue = null;
    } catch (err) {
      mergeError = err instanceof Error ? err.message : 'Merge failed';
    } finally {
      mergePending = false;
    }
  }

  // Unified list for rendering
  const currentList = $derived<Array<{ id: number; name: string; book_count: number } | { value: string; edition_count: number }>>(
    activeTab === 'authors' ? filteredAuthors :
    activeTab === 'tags' ? filteredTags :
    activeTab === 'series' ? filteredSeries :
    activeTab === 'publishers' ? filteredPublishers :
    filteredLanguages
  );

  const tabCounts = $derived({
    authors: authors.length,
    tags: tags.length,
    series: series.length,
    publishers: publishers.length,
    languages: languages.length,
  });
</script>

<div class="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:px-8">
  <div class="mb-6">
    <h1 class="text-3xl font-bold tracking-tight">Metadata Manager</h1>
    <p class="mt-1 text-muted-foreground">Rename, merge, and standardize Authors, Tags, Series, Publishers, and Languages</p>
  </div>

  <!-- Tabs -->
  <div class="mb-5 flex gap-1 rounded-lg border bg-muted/40 p-1 w-fit flex-wrap">
    {#each (['authors', 'tags', 'series', 'publishers', 'languages'] as const) as tab}
      <button
        onclick={() => switchTab(tab)}
        class="flex items-center gap-2 rounded-md px-4 py-1.5 text-sm font-medium transition-colors {activeTab === tab ? 'bg-background shadow-sm text-foreground' : 'text-muted-foreground hover:text-foreground'}"
      >
        {tab.charAt(0).toUpperCase() + tab.slice(1)}
        <span class="text-xs tabular-nums">{tabCounts[tab]}</span>
      </button>
    {/each}
  </div>

  <!-- Merge mode banner -->
  {#if mergeSourceId || mergeSourceValue}
    {@const sourceName = mergeSourceId
      ? (currentList as any[]).find((i: any) => i.id === mergeSourceId)?.name
      : mergeSourceValue}
    <div class="mb-4 flex items-center justify-between rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3">
      <p class="text-sm">
        <span class="font-medium">Merging "{sourceName}"</span>
        — click another entry to absorb it (all editions reassigned to target)
      </p>
      <Button variant="ghost" size="sm" onclick={cancelMerge}>Cancel</Button>
    </div>
    {#if mergeError}
      <p class="mb-3 text-sm text-destructive">{mergeError}</p>
    {/if}
  {/if}

  {#if globalError}
    <p class="mb-3 text-sm text-destructive">{globalError}</p>
  {/if}

  <!-- Filter -->
  <div class="mb-4">
    <Input placeholder="Filter by name…" bind:value={filterText} class="max-w-sm" />
  </div>

  <!-- Loading state -->
  {#if loadingField}
    <p class="py-12 text-center text-sm text-muted-foreground">Loading...</p>
  {:else if currentList.length === 0}
    <p class="py-12 text-center text-sm text-muted-foreground">No entries found.</p>
  {:else if isFieldTab}
    <!-- String-based list (publishers/languages) -->
    <div class="divide-y rounded-lg border">
      {#each currentList as item}
        {@const fv = item as FieldValueDetail}
        {@const isEditing = editingValue === fv.value}
        {@const isMergeSource = mergeSourceValue === fv.value}
        {@const isTarget = mergeSourceValue && !isMergeSource}
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <div
          class="group flex items-center gap-3 px-4 py-2.5 transition-colors {isMergeSource ? 'bg-amber-500/10' : isTarget ? 'cursor-pointer hover:bg-green-500/10' : 'hover:bg-muted/30'}"
          onclick={() => { if (isTarget) mergeFieldInto(fv.value); }}
        >
          {#if isEditing}
            <input
              bind:value={editingNewValue}
              class="h-7 flex-1 rounded border bg-background px-2 py-0 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              onkeydown={(e) => { if (e.key === 'Enter') { e.preventDefault(); commitFieldRename(); } else if (e.key === 'Escape') cancelEdit(); }}
            />
            {#if renameError}<span class="text-xs text-destructive shrink-0">{renameError}</span>{/if}
            <button onclick={(e) => { e.stopPropagation(); commitFieldRename(); }} class="text-green-600 hover:text-green-700 shrink-0" title="Save">
              <Check class="h-4 w-4" />
            </button>
            <button onclick={(e) => { e.stopPropagation(); cancelEdit(); }} class="text-muted-foreground hover:text-foreground shrink-0" title="Cancel">
              <X class="h-4 w-4" />
            </button>
          {:else}
            <span class="flex-1 text-sm {isMergeSource ? 'font-semibold text-amber-700 dark:text-amber-400' : 'font-medium'}">{fv.value}</span>
            <Badge variant="secondary" class="shrink-0 tabular-nums text-xs">
              <BookOpen class="mr-1 h-2.5 w-2.5" />{fv.edition_count}
            </Badge>
            {#if !mergeSourceValue}
              <div class="invisible flex shrink-0 items-center gap-1.5 group-hover:visible">
                <button onclick={(e) => { e.stopPropagation(); startFieldEdit(fv.value); }} title="Rename" class="text-muted-foreground/50 hover:text-foreground transition-colors">
                  <Pencil class="h-3.5 w-3.5" />
                </button>
                <button onclick={(e) => { e.stopPropagation(); startFieldMerge(fv.value); }} title="Merge into another" class="text-muted-foreground/50 hover:text-foreground transition-colors">
                  <GitMerge class="h-3.5 w-3.5" />
                </button>
              </div>
            {:else if isMergeSource}
              <span class="shrink-0 text-xs font-medium text-amber-600">source</span>
            {:else}
              <span class="invisible shrink-0 text-xs text-green-600 group-hover:visible">← merge here</span>
            {/if}
          {/if}
        </div>
      {/each}
    </div>
  {:else}
    <!-- ID-based list (authors/tags/series) -->
    <div class="divide-y rounded-lg border">
      {#each currentList as item}
        {@const idItem = item as AuthorDetail}
        {@const isEditing = editingId === idItem.id}
        {@const isMergeSource = mergeSourceId === idItem.id}
        {@const isTarget = mergeSourceId && !isMergeSource}
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <div
          class="group flex items-center gap-3 px-4 py-2.5 transition-colors {isMergeSource ? 'bg-amber-500/10' : isTarget ? 'cursor-pointer hover:bg-green-500/10' : 'hover:bg-muted/30'}"
          onclick={() => { if (isTarget) mergeInto(idItem.id); }}
        >
          {#if isEditing}
            <input
              bind:value={editingName}
              class="h-7 flex-1 rounded border bg-background px-2 py-0 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              onkeydown={(e) => { if (e.key === 'Enter') { e.preventDefault(); commitRename(); } else if (e.key === 'Escape') cancelEdit(); }}
            />
            {#if renameError}<span class="text-xs text-destructive shrink-0">{renameError}</span>{/if}
            <button onclick={(e) => { e.stopPropagation(); commitRename(); }} class="text-green-600 hover:text-green-700 shrink-0" title="Save">
              <Check class="h-4 w-4" />
            </button>
            <button onclick={(e) => { e.stopPropagation(); cancelEdit(); }} class="text-muted-foreground hover:text-foreground shrink-0" title="Cancel">
              <X class="h-4 w-4" />
            </button>
          {:else}
            <span class="flex-1 text-sm {isMergeSource ? 'font-semibold text-amber-700 dark:text-amber-400' : 'font-medium'}">{idItem.name}</span>
            <Badge variant="secondary" class="shrink-0 tabular-nums text-xs">
              <BookOpen class="mr-1 h-2.5 w-2.5" />{idItem.book_count}
            </Badge>
            {#if !mergeSourceId}
              <div class="invisible flex shrink-0 items-center gap-1.5 group-hover:visible">
                <button onclick={(e) => { e.stopPropagation(); startEdit(idItem.id, idItem.name); }} title="Rename" class="text-muted-foreground/50 hover:text-foreground transition-colors">
                  <Pencil class="h-3.5 w-3.5" />
                </button>
                <button onclick={(e) => { e.stopPropagation(); startMerge(idItem.id); }} title="Merge into another" class="text-muted-foreground/50 hover:text-foreground transition-colors">
                  <GitMerge class="h-3.5 w-3.5" />
                </button>
                {#if idItem.book_count === 0}
                  <button onclick={(e) => { e.stopPropagation(); deleteEntity(idItem.id); }} title="Delete (no books)" class="text-muted-foreground/50 hover:text-destructive transition-colors">
                    <Trash2 class="h-3.5 w-3.5" />
                  </button>
                {/if}
              </div>
            {:else if isMergeSource}
              <span class="shrink-0 text-xs font-medium text-amber-600">source</span>
            {:else}
              <span class="invisible shrink-0 text-xs text-green-600 group-hover:visible">← merge here</span>
            {/if}
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>
