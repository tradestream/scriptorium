<!--
  Reading-list index. Mirrors the shape of /collections — list, create,
  delete — but without smart-filter / pin-to-Kobo wiring (deferred).
  Drag-to-reorder lives on the detail page since order matters per-list.
-->
<script lang="ts">
  import { Button } from "$lib/components/ui/button";
  import { Input } from "$lib/components/ui/input";
  import { ListOrdered, Plus, Trash2, X, BookOpen } from "lucide-svelte";
  import * as api from "$lib/api/client";
  import type { ReadingList } from "$lib/types/index";

  let lists = $state<ReadingList[]>([]);
  let loading = $state(true);
  let showDialog = $state(false);
  let formName = $state('');
  let formDescription = $state('');
  let saving = $state(false);
  let formError = $state('');

  async function load() {
    loading = true;
    try { lists = await api.getReadingLists(); } finally { loading = false; }
  }
  $effect(() => { load(); });

  function openCreate() {
    formName = ''; formDescription = ''; formError = ''; showDialog = true;
  }

  async function submit() {
    if (!formName.trim()) { formError = 'Name is required'; return; }
    saving = true; formError = '';
    try {
      await api.createReadingList({
        name: formName.trim(),
        description: formDescription.trim() || null,
      });
      showDialog = false;
      await load();
    } catch (err: any) {
      formError = err?.message ?? 'Save failed';
    } finally {
      saving = false;
    }
  }

  async function remove(list: ReadingList) {
    if (!confirm(`Delete reading list "${list.name}"?`)) return;
    await api.deleteReadingList(list.id);
    await load();
  }

  function fmtDate(iso: string): string {
    return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
  }
</script>

<div class="mx-auto max-w-5xl px-4 py-8 sm:px-6">
  <div class="mb-6 flex items-center gap-3">
    <ListOrdered class="h-6 w-6 text-muted-foreground/50" />
    <h1 class="text-2xl font-bold tracking-tight flex-1">Reading Lists</h1>
    <Button onclick={openCreate} size="sm">
      <Plus class="h-3.5 w-3.5 mr-1" /> New
    </Button>
  </div>

  <p class="mb-6 max-w-prose text-sm text-muted-foreground">
    Ordered sequences of books to read in turn. Unlike shelves and collections,
    the position matters — use these for arc-reading comics, course curricula,
    or "things to read this year, in this order."
  </p>

  {#if loading}
    <p class="text-sm text-muted-foreground">Loading…</p>
  {:else if lists.length === 0}
    <div class="flex flex-col items-center gap-3 py-16 text-center text-muted-foreground">
      <ListOrdered class="h-12 w-12 opacity-30" />
      <p class="text-sm">No reading lists yet.</p>
      <Button onclick={openCreate} variant="outline" size="sm">
        <Plus class="h-3.5 w-3.5 mr-1" /> Create one
      </Button>
    </div>
  {:else}
    <div class="divide-y rounded-lg border bg-card">
      {#each lists as list (list.id)}
        <div class="flex items-center gap-3 px-4 py-3 hover:bg-muted/40 transition-colors">
          <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-muted">
            <ListOrdered class="h-5 w-5 text-muted-foreground/60" />
          </div>
          <a href="/reading-lists/{list.id}" class="min-w-0 flex-1">
            <p class="truncate text-sm font-medium">{list.name}</p>
            <p class="mt-0.5 truncate text-xs text-muted-foreground">
              {list.entry_count} {list.entry_count === 1 ? 'entry' : 'entries'}
              {#if list.description} · {list.description}{/if}
              <span class="ml-1 opacity-60">· updated {fmtDate(list.updated_at)}</span>
            </p>
          </a>
          <button
            onclick={() => remove(list)}
            class="rounded-md p-1.5 text-muted-foreground/40 hover:text-destructive hover:bg-destructive/10 transition-colors"
            title="Delete reading list"
            aria-label="Delete"
          >
            <Trash2 class="h-3.5 w-3.5" />
          </button>
        </div>
      {/each}
    </div>
  {/if}
</div>

{#if showDialog}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
    role="dialog"
    aria-modal="true"
  >
    <div class="w-full max-w-md rounded-lg border bg-background p-5 shadow-xl">
      <div class="mb-4 flex items-center justify-between">
        <h2 class="text-base font-semibold">New reading list</h2>
        <button
          onclick={() => (showDialog = false)}
          class="rounded-md p-1 text-muted-foreground hover:bg-muted"
          aria-label="Close"
        >
          <X class="h-4 w-4" />
        </button>
      </div>
      <div class="space-y-3">
        <div>
          <label for="rl-name" class="text-xs font-medium text-muted-foreground">Name</label>
          <Input id="rl-name" bind:value={formName} placeholder="Court of Owls arc" />
        </div>
        <div>
          <label for="rl-desc" class="text-xs font-medium text-muted-foreground">Description (optional)</label>
          <Input id="rl-desc" bind:value={formDescription} placeholder="Read in this order" />
        </div>
        {#if formError}
          <p class="text-xs text-destructive">{formError}</p>
        {/if}
        <div class="flex justify-end gap-2 pt-2">
          <Button variant="outline" size="sm" onclick={() => (showDialog = false)} disabled={saving}>Cancel</Button>
          <Button size="sm" onclick={submit} disabled={saving}>
            <BookOpen class="h-3.5 w-3.5 mr-1" /> {saving ? 'Saving…' : 'Create'}
          </Button>
        </div>
      </div>
    </div>
  </div>
{/if}
