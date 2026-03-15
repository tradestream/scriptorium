<script lang="ts">
  import { BookCopy, Plus, Trash2, Pencil, ChevronRight, Loader2 } from 'lucide-svelte';
  import * as api from '$lib/api/client';
  import type { Notebook } from '$lib/api/client';

  let notebooks = $state<Notebook[]>([]);
  let loading = $state(true);

  // Create form
  let showCreate = $state(false);
  let newName = $state('');
  let newDesc = $state('');
  let creating = $state(false);

  // Edit state
  let editingId = $state<number | null>(null);
  let editName = $state('');
  let editDesc = $state('');
  let saving = $state(false);

  async function load() {
    loading = true;
    try {
      notebooks = await api.getNotebooks();
    } catch (e) {
      console.error(e);
    } finally {
      loading = false;
    }
  }

  async function create() {
    if (!newName.trim()) return;
    creating = true;
    try {
      const nb = await api.createNotebook({ name: newName.trim(), description: newDesc.trim() || undefined });
      notebooks = [nb, ...notebooks];
      newName = '';
      newDesc = '';
      showCreate = false;
    } catch (e) {
      console.error(e);
    } finally {
      creating = false;
    }
  }

  function startEdit(nb: Notebook) {
    editingId = nb.id;
    editName = nb.name;
    editDesc = nb.description ?? '';
  }

  async function saveEdit() {
    if (!editingId || !editName.trim()) return;
    saving = true;
    try {
      const updated = await api.updateNotebook(editingId, { name: editName.trim(), description: editDesc.trim() || undefined });
      notebooks = notebooks.map(nb => nb.id === editingId ? updated : nb);
      editingId = null;
    } catch (e) {
      console.error(e);
    } finally {
      saving = false;
    }
  }

  async function remove(id: number) {
    if (!confirm('Delete this notebook and all its entries?')) return;
    try {
      await api.deleteNotebook(id);
      notebooks = notebooks.filter(nb => nb.id !== id);
    } catch (e) {
      console.error(e);
    }
  }

  $effect(() => { load(); });
</script>

<div class="mx-auto max-w-3xl space-y-6 p-6">
  <div class="flex items-center gap-3">
    <BookCopy class="h-6 w-6 text-primary" />
    <div>
      <h1 class="text-2xl font-semibold">Notebooks</h1>
      <p class="text-sm text-muted-foreground">Named collections of marginalia across books</p>
    </div>
    <button
      class="ml-auto flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm transition-colors hover:bg-accent"
      onclick={() => { showCreate = !showCreate; }}
    >
      <Plus class="h-3.5 w-3.5" /> New notebook
    </button>
  </div>

  {#if showCreate}
    <div class="rounded-lg border bg-muted/20 p-4 space-y-3">
      <p class="text-sm font-medium">New notebook</p>
      <input
        type="text"
        placeholder="Name"
        bind:value={newName}
        class="w-full rounded-md border bg-background px-3 py-1.5 text-sm outline-none focus:ring-1 focus:ring-ring"
        onkeydown={(e) => { if (e.key === 'Enter') create(); if (e.key === 'Escape') showCreate = false; }}
      />
      <input
        type="text"
        placeholder="Description (optional)"
        bind:value={newDesc}
        class="w-full rounded-md border bg-background px-3 py-1.5 text-sm outline-none focus:ring-1 focus:ring-ring"
        onkeydown={(e) => { if (e.key === 'Enter') create(); }}
      />
      <div class="flex gap-2">
        <button
          onclick={create}
          disabled={creating || !newName.trim()}
          class="rounded-md bg-primary px-4 py-1.5 text-sm text-primary-foreground disabled:opacity-50 transition-opacity"
        >{creating ? 'Creating…' : 'Create'}</button>
        <button
          onclick={() => { showCreate = false; newName = ''; newDesc = ''; }}
          class="rounded-md border px-4 py-1.5 text-sm transition-colors hover:bg-accent"
        >Cancel</button>
      </div>
    </div>
  {/if}

  {#if loading}
    <div class="flex justify-center py-16">
      <Loader2 class="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  {:else if notebooks.length === 0}
    <div class="py-16 text-center text-muted-foreground">
      <BookCopy class="mx-auto mb-3 h-10 w-10 opacity-20" />
      <p class="text-sm">No notebooks yet. Create one to collect marginalia across books.</p>
    </div>
  {:else}
    <div class="space-y-2">
      {#each notebooks as nb (nb.id)}
        {#if editingId === nb.id}
          <div class="rounded-lg border bg-muted/20 p-4 space-y-3">
            <input
              type="text"
              bind:value={editName}
              class="w-full rounded-md border bg-background px-3 py-1.5 text-sm outline-none focus:ring-1 focus:ring-ring"
              onkeydown={(e) => { if (e.key === 'Enter') saveEdit(); if (e.key === 'Escape') editingId = null; }}
            />
            <input
              type="text"
              placeholder="Description (optional)"
              bind:value={editDesc}
              class="w-full rounded-md border bg-background px-3 py-1.5 text-sm outline-none focus:ring-1 focus:ring-ring"
              onkeydown={(e) => { if (e.key === 'Enter') saveEdit(); }}
            />
            <div class="flex gap-2">
              <button
                onclick={saveEdit}
                disabled={saving || !editName.trim()}
                class="rounded-md bg-primary px-4 py-1.5 text-sm text-primary-foreground disabled:opacity-50"
              >{saving ? 'Saving…' : 'Save'}</button>
              <button
                onclick={() => editingId = null}
                class="rounded-md border px-4 py-1.5 text-sm hover:bg-accent"
              >Cancel</button>
            </div>
          </div>
        {:else}
          <div class="group flex items-center gap-3 rounded-lg border p-4 transition-colors hover:bg-muted/30">
            <a href="/notebooks/{nb.id}" class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <p class="font-medium truncate">{nb.name}</p>
                <span class="shrink-0 rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
                  {nb.entry_count} {nb.entry_count === 1 ? 'entry' : 'entries'}
                </span>
              </div>
              {#if nb.description}
                <p class="mt-0.5 text-sm text-muted-foreground truncate">{nb.description}</p>
              {/if}
              <p class="mt-1 text-[11px] text-muted-foreground/60">
                {new Date(nb.created_at).toLocaleDateString()}
              </p>
            </a>
            <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
              <button
                onclick={() => startEdit(nb)}
                class="rounded p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
                title="Edit"
              >
                <Pencil class="h-3.5 w-3.5" />
              </button>
              <button
                onclick={() => remove(nb.id)}
                class="rounded p-1.5 text-muted-foreground hover:bg-destructive/10 hover:text-destructive transition-colors"
                title="Delete"
              >
                <Trash2 class="h-3.5 w-3.5" />
              </button>
            </div>
            <a href="/notebooks/{nb.id}" class="shrink-0 text-muted-foreground/40 group-hover:text-muted-foreground transition-colors">
              <ChevronRight class="h-4 w-4" />
            </a>
          </div>
        {/if}
      {/each}
    </div>
  {/if}
</div>
