<script lang="ts">
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { ListOrdered, Pencil, Save, X, BookOpen, Download } from 'lucide-svelte';
  import { DragDropProvider } from '@dnd-kit-svelte/svelte';
  import { move } from '@dnd-kit/helpers';
  import * as api from '$lib/api/client';

  // ``@dnd-kit/helpers`` and ``@dnd-kit-svelte/svelte`` resolve
  // ``@dnd-kit/abstract`` at different versions, producing two
  // nominally-distinct ``Position`` types. Cast through ``never`` once
  // here so the call sites stay readable.
  function reorderIds<T extends string | number>(ids: T[], event: unknown): T[] {
    return move(ids as any, event as never) as T[];
  }
  import SortableReadingListEntry from '$lib/components/SortableReadingListEntry.svelte';
  import { Button } from '$lib/components/ui/button';
  import { Input } from '$lib/components/ui/input';
  import type { ReadingListDetail, ReadingListEntry } from '$lib/types/index';

  let listId = $derived(parseInt(page.params.id ?? '0', 10));
  let detail = $state<ReadingListDetail | null>(null);
  let entries = $state<ReadingListEntry[]>([]);
  let loading = $state(true);
  let editingMeta = $state(false);
  let editName = $state('');
  let editDescription = $state('');
  let dirtyOrder = $state(false);
  let savingOrder = $state(false);

  async function load() {
    loading = true;
    try {
      detail = await api.getReadingList(listId);
      entries = [...detail.entries];
      editName = detail.name;
      editDescription = detail.description ?? '';
      dirtyOrder = false;
    } finally {
      loading = false;
    }
  }
  $effect(() => { if (listId) void load(); });

  async function saveMeta() {
    if (!detail) return;
    await api.updateReadingList(detail.id, {
      name: editName.trim() || detail.name,
      description: editDescription.trim() || null,
    });
    editingMeta = false;
    await load();
  }

  async function commitOrder() {
    if (!detail || !dirtyOrder) return;
    savingOrder = true;
    try {
      await api.reorderReadingList(detail.id, entries.map((e) => e.id));
      dirtyOrder = false;
    } finally {
      savingOrder = false;
    }
  }

  async function removeEntry(entryId: number) {
    if (!detail) return;
    await api.removeReadingListEntry(detail.id, entryId);
    await load();
  }

  async function deleteList() {
    if (!detail) return;
    if (!confirm(`Delete reading list "${detail.name}"?`)) return;
    await api.deleteReadingList(detail.id);
    goto('/reading-lists');
  }
</script>

<div class="mx-auto max-w-4xl px-4 py-8 sm:px-6">
  <nav class="mb-5 flex items-center gap-1.5 text-xs text-muted-foreground">
    <a href="/reading-lists" class="hover:text-foreground transition-colors">Reading Lists</a>
    <span>/</span>
    <span class="text-foreground">{detail?.name ?? 'Loading…'}</span>
  </nav>

  {#if loading || !detail}
    <p class="text-sm text-muted-foreground">Loading…</p>
  {:else}
    <div class="mb-8 flex items-start gap-3">
      <ListOrdered class="mt-1 h-6 w-6 shrink-0 text-muted-foreground/50" />
      <div class="min-w-0 flex-1">
        {#if editingMeta}
          <div class="space-y-2">
            <Input bind:value={editName} class="text-2xl font-bold" />
            <Input bind:value={editDescription} placeholder="Description (optional)" />
            <div class="flex gap-2">
              <Button size="sm" onclick={saveMeta}><Save class="h-3.5 w-3.5 mr-1" /> Save</Button>
              <Button size="sm" variant="outline" onclick={() => { editingMeta = false; if (detail) { editName = detail.name; editDescription = detail.description ?? ''; } }}><X class="h-3.5 w-3.5 mr-1" /> Cancel</Button>
            </div>
          </div>
        {:else}
          <div class="flex items-center gap-3">
            <h1 class="text-2xl font-bold tracking-tight">{detail.name}</h1>
            <button
              onclick={() => (editingMeta = true)}
              class="flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors"
            >
              <Pencil class="h-3 w-3" /> Edit
            </button>
          </div>
          {#if detail.description}
            <p class="mt-1 max-w-prose text-sm text-muted-foreground">{detail.description}</p>
          {/if}
          <p class="mt-1.5 text-xs text-muted-foreground">
            {entries.length} {entries.length === 1 ? 'entry' : 'entries'}
            {#if detail.source} · imported from {detail.source}{/if}
          </p>
        {/if}
      </div>
      {#if !editingMeta}
        <a
          href={api.readingListExportCblUrl(detail.id)}
          target="_blank"
          rel="noopener"
          class="inline-flex items-center gap-1 rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-muted transition-colors"
          title="Export as CBL (Kavita / Komga compatible)"
        >
          <Download class="h-3.5 w-3.5" /> CBL
        </a>
        <Button size="sm" variant="outline" onclick={deleteList}>Delete</Button>
      {/if}
    </div>

    {#if entries.length === 0}
      <div class="flex flex-col items-center gap-4 py-20 text-center">
        <div class="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
          <BookOpen class="h-7 w-7 text-muted-foreground/40" />
        </div>
        <div>
          <p class="font-medium text-foreground">Empty reading list</p>
          <p class="mt-1 text-sm text-muted-foreground">
            Add books from any book page using the "Add to reading list" action.
          </p>
        </div>
      </div>
    {:else}
      <div class="space-y-2">
        <DragDropProvider
          onDragOver={(event) => {
            const ids = entries.map((e) => e.id);
            const reordered = reorderIds(ids, event);
            const byId = new Map(entries.map((e) => [e.id, e]));
            const next = reordered
              .map((id) => byId.get(id))
              .filter((e): e is ReadingListEntry => e !== undefined);
            // Detect a real change before flagging dirty so passive
            // hover events don't trip the "Save order" affordance.
            for (let i = 0; i < next.length; i++) {
              if (next[i].id !== entries[i].id) { dirtyOrder = true; break; }
            }
            entries = next;
          }}
        >
          {#each entries as entry, i (entry.id)}
            <SortableReadingListEntry {entry} index={i} onRemove={() => removeEntry(entry.id)} />
          {/each}
        </DragDropProvider>

        {#if dirtyOrder}
          <div class="flex items-center gap-2 pt-3">
            <Button size="sm" onclick={commitOrder} disabled={savingOrder}>
              <Save class="h-3.5 w-3.5 mr-1" /> {savingOrder ? 'Saving…' : 'Save order'}
            </Button>
            <Button size="sm" variant="outline" onclick={load}>
              <X class="h-3.5 w-3.5 mr-1" /> Discard
            </Button>
          </div>
        {/if}
      </div>
    {/if}
  {/if}
</div>
