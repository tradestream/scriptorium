<script lang="ts">
  import { BookOpen, Check, Layers, Pencil, X, Save } from 'lucide-svelte';
  import { DragDropProvider } from '@dnd-kit-svelte/svelte';
  import { move } from '@dnd-kit/helpers';
  import SortableSeriesEntry from '$lib/components/SortableSeriesEntry.svelte';
  import * as api from '$lib/api/client';
  import { invalidateAll } from '$app/navigation';
  import type { SeriesEntry } from '$lib/types/index';

  let { data } = $props();

  // ── Read view ────────────────────────────────────────────────────────────────

  const grouped = $derived.by(() => {
    const allNull = data.entries.every((e: SeriesEntry) => e.volume == null);
    if (allNull) {
      return [{ label: null as string | null, entries: data.entries as SeriesEntry[] }];
    }
    const map = new Map<string, SeriesEntry[]>();
    for (const entry of data.entries as SeriesEntry[]) {
      const key = entry.volume ?? 'Ungrouped';
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(entry);
    }
    return Array.from(map.entries()).map(([label, entries]) => ({ label, entries }));
  });

  const hasVolumes = $derived(grouped.length > 1 || grouped[0]?.label != null);

  function coverUrl(entry: SeriesEntry): string {
    return api.bookCoverUrl(entry.book) ?? '';
  }

  function formatPosition(pos: number | null): string {
    if (pos == null) return '';
    return Number.isInteger(pos) ? String(pos) : pos.toFixed(1);
  }

  function statusLabel(status: SeriesEntry['read_status']) {
    if (status === 'completed') return 'Read';
    if (status === 'reading') return 'Reading';
    if (status === 'want_to_read') return 'Want to read';
    return null;
  }

  function statusClass(status: SeriesEntry['read_status']) {
    if (status === 'completed') return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400';
    if (status === 'reading') return 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400';
    return 'bg-muted text-muted-foreground';
  }

  // ── Edit mode ────────────────────────────────────────────────────────────────

  let editing = $state(false);
  type EditEntry = SeriesEntry & { _key: number };
  let editEntries = $state<EditEntry[]>([]);
  let saving = $state(false);
  let saveError = $state('');

  function startEdit() {
    editEntries = (data.entries as SeriesEntry[]).map(e => ({ ...e, _key: e.book.id }));
    editing = true;
    saveError = '';
  }

  function cancelEdit() {
    editing = false;
    editEntries = [];
  }

  async function saveEdit() {
    saving = true;
    saveError = '';
    try {
      await api.updateSeriesEntries(
        data.id,
        editEntries.map(e => ({
          book_id: e.book.id,
          position: e.position ?? null,
          volume: e.volume ?? null,
          arc: e.arc ?? null,
        }))
      );
      editing = false;
      await invalidateAll();
    } catch (err: any) {
      saveError = err?.message ?? 'Save failed';
    } finally {
      saving = false;
    }
  }

  function removeEntry(index: number) {
    editEntries = editEntries.filter((_, i) => i !== index);
  }
</script>

<div class="mx-auto max-w-4xl px-4 py-8 sm:px-6">

  <!-- Breadcrumb -->
  <nav class="mb-5 flex items-center gap-1.5 text-xs text-muted-foreground">
    <a href="/browse/series" class="hover:text-foreground transition-colors">Series</a>
    <span>/</span>
    <span class="text-foreground">{data.name}</span>
  </nav>

  <!-- Header -->
  <div class="mb-8">
    <div class="flex items-start gap-3">
      <Layers class="mt-1 h-6 w-6 shrink-0 text-muted-foreground/50" />
      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-3">
          <h1 class="text-2xl font-bold tracking-tight">{data.name}</h1>
          {#if !editing}
            <button
              onclick={startEdit}
              class="flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors"
              title="Edit series order"
            >
              <Pencil class="h-3 w-3" /> Edit order
            </button>
          {/if}
        </div>
        {#if data.description}
          <p class="mt-1 max-w-prose text-sm text-muted-foreground">{data.description}</p>
        {/if}
        <p class="mt-1.5 text-xs text-muted-foreground">
          {data.book_count} {data.book_count === 1 ? 'entry' : 'entries'}
        </p>
      </div>
    </div>
  </div>

  {#if editing}
    <!-- ── Edit mode ──────────────────────────────────────────────────────── -->
    <div class="space-y-2">
      <!-- Column headers -->
      <div class="flex items-center gap-3 px-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/50">
        <span class="w-4 shrink-0"></span>
        <span class="w-7 shrink-0"></span>
        <span class="min-w-0 flex-1">Title</span>
        <div class="flex shrink-0 gap-1.5">
          <span class="w-14 text-center">Pos.</span>
          <span class="w-16 text-center">Volume</span>
          <span class="w-20 text-center">Arc</span>
        </div>
        <span class="w-3.5 shrink-0"></span>
      </div>

      <DragDropProvider onDragOver={(event) => { editEntries = move(editEntries, event as any); }}>
        {#each editEntries as entry, i (entry._key)}
          <SortableSeriesEntry {entry} index={i} onRemove={() => removeEntry(i)} />
        {/each}
      </DragDropProvider>

      <!-- Save / cancel -->
      <div class="flex items-center gap-2 pt-3">
        <button
          onclick={saveEdit}
          disabled={saving}
          class="flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          <Save class="h-3.5 w-3.5" />
          {saving ? 'Saving…' : 'Save'}
        </button>
        <button
          onclick={cancelEdit}
          disabled={saving}
          class="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <X class="h-3.5 w-3.5" /> Cancel
        </button>
        {#if saveError}
          <p class="text-xs text-destructive">{saveError}</p>
        {/if}
      </div>
    </div>

  {:else}
    <!-- ── Read view ──────────────────────────────────────────────────────── -->

    {#if data.entries.length === 0}
      <div class="flex flex-col items-center gap-4 py-20 text-center">
        <div class="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
          <BookOpen class="h-7 w-7 text-muted-foreground/40" />
        </div>
        <div>
          <p class="font-medium text-foreground">No entries yet</p>
          <p class="mt-1 text-sm text-muted-foreground">Books in this series haven't been catalogued yet.</p>
        </div>
      </div>

    {:else}
      <div class="space-y-10">
        {#each grouped as group}
          <section>
            {#if hasVolumes && group.label}
              <h2 class="mb-4 border-b pb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                {group.label}
              </h2>
            {/if}

            <div class="divide-y">
              {#each group.entries as entry}
                {@const cover = coverUrl(entry)}
                {@const pos = formatPosition(entry.position)}
                {@const badge = statusLabel(entry.read_status)}
                <a
                  href="/book/{entry.book.id}"
                  class="group -mx-2 flex items-center gap-4 rounded-md px-2 py-3 transition-colors hover:bg-muted/40"
                >
                  <!-- Cover thumbnail -->
                  <div class="relative h-16 w-11 shrink-0 overflow-hidden rounded shadow-sm">
                    {#if cover}
                      <img src={cover} alt="" class="h-full w-full object-cover" loading="lazy" />
                    {:else}
                      <div class="flex h-full w-full items-center justify-center bg-muted/60">
                        <BookOpen class="h-4 w-4 text-muted-foreground/30" />
                      </div>
                    {/if}
                    {#if entry.read_status === 'completed'}
                      <div class="absolute inset-0 flex items-end justify-end bg-green-500/10 p-0.5">
                        <Check class="h-3 w-3 text-green-600" />
                      </div>
                    {/if}
                  </div>

                  <!-- Metadata -->
                  <div class="min-w-0 flex-1">
                    <div class="flex items-baseline gap-1.5">
                      {#if pos}
                        <span class="shrink-0 font-mono text-xs font-semibold tabular-nums text-muted-foreground">
                          #{pos}
                        </span>
                      {/if}
                      <span class="truncate text-sm font-medium">{entry.book.title}</span>
                    </div>
                    {#if entry.book.authors?.length}
                      <p class="mt-0.5 truncate text-xs text-muted-foreground">
                        {entry.book.authors.map((a: { name: string }) => a.name).join(', ')}
                      </p>
                    {/if}
                    {#if entry.arc}
                      <p class="mt-0.5 text-[10px] italic text-muted-foreground/60">{entry.arc}</p>
                    {/if}
                  </div>

                  <!-- Read status + year -->
                  <div class="flex shrink-0 flex-col items-end gap-1.5">
                    {#if badge}
                      <span class="rounded-full px-2 py-0.5 text-[10px] font-medium {statusClass(entry.read_status)}">
                        {badge}
                      </span>
                    {/if}
                    {#if entry.book.published_date}
                      <span class="tabular-nums text-[10px] text-muted-foreground/50">
                        {new Date(entry.book.published_date).getFullYear()}
                      </span>
                    {/if}
                  </div>
                </a>
              {/each}
            </div>
          </section>
        {/each}
      </div>
    {/if}
  {/if}
</div>
