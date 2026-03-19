<script lang="ts">
  import { Card, CardContent, CardHeader, CardTitle } from "$lib/components/ui/card";
  import { Button } from "$lib/components/ui/button";
  import { Input } from "$lib/components/ui/input";
  import { Badge } from "$lib/components/ui/badge";
  import { Layers, Plus, Pencil, Trash2, X } from "lucide-svelte";
  import * as api from "$lib/api/client";
  import type { Collection } from "$lib/types/index";

  let collections = $state<Collection[]>([]);
  let loading = $state(true);
  let showDialog = $state(false);
  let editing = $state<Collection | null>(null);
  let formName = $state('');
  let formDescription = $state('');
  let saving = $state(false);
  let formError = $state('');

  async function load() {
    loading = true;
    try { collections = await api.getCollections(); } finally { loading = false; }
  }

  $effect(() => { load(); });

  function openCreate() {
    editing = null; formName = ''; formDescription = ''; formError = ''; showDialog = true;
  }

  function openEdit(col: Collection) {
    editing = col; formName = col.name; formDescription = col.description ?? ''; formError = ''; showDialog = true;
  }

  async function save() {
    if (!formName.trim()) { formError = 'Name is required'; return; }
    saving = true; formError = '';
    try {
      if (editing) {
        await api.updateCollection(editing.id, { name: formName.trim(), description: formDescription.trim() || null });
      } else {
        await api.createCollection({ name: formName.trim(), description: formDescription.trim() || null });
      }
      showDialog = false;
      await load();
    } catch (e) {
      formError = e instanceof Error ? e.message : 'Failed';
    } finally { saving = false; }
  }

  async function remove(col: Collection) {
    if (!confirm(`Delete "${col.name}"?`)) return;
    try { await api.deleteCollection(col.id); await load(); }
    catch (e) { alert(e instanceof Error ? e.message : 'Failed'); }
  }
</script>

<div class="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:px-8">
  <div class="mb-6 flex items-center justify-between">
    <div>
      <h1 class="text-3xl font-bold tracking-tight">Collections</h1>
      <p class="mt-1 text-muted-foreground">Thematic groupings — universes, publishers, genres</p>
    </div>
    <Button onclick={openCreate}><Plus class="mr-2 h-4 w-4" /> New Collection</Button>
  </div>

  {#if loading}
    <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {#each [1,2,3] as _}
        <Card class="animate-pulse"><CardHeader><div class="h-5 w-1/2 rounded bg-muted"></div></CardHeader></Card>
      {/each}
    </div>
  {:else if collections.length > 0}
    <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {#each collections as col}
        <Card class="transition-shadow hover:shadow-md">
          <CardHeader class="flex flex-row items-start justify-between pb-2">
            <div class="flex-1 min-w-0">
              <a href="/collections/{col.id}" class="hover:underline">
                <CardTitle class="text-lg truncate">{col.name}</CardTitle>
              </a>
              <div class="mt-1 flex gap-1.5">
                {#if col.sync_to_kobo}
                  <Badge variant="outline" class="text-xs border-blue-300 text-blue-600 dark:border-blue-700 dark:text-blue-400">
                    Kobo
                  </Badge>
                {/if}
                {#if col.is_smart}
                  <Badge variant="secondary" class="text-xs">Smart</Badge>
                {/if}
                {#if col.is_pinned}
                  <Badge variant="secondary" class="text-xs">Pinned</Badge>
                {/if}
              </div>
              {#if col.description}
                <p class="mt-1 text-sm text-muted-foreground line-clamp-2">{col.description}</p>
              {/if}
            </div>
            <div class="flex shrink-0 gap-1 ml-2">
              <Button variant="ghost" size="icon" class="h-7 w-7" onclick={() => openEdit(col)}><Pencil class="h-3.5 w-3.5" /></Button>
              <Button variant="ghost" size="icon" class="h-7 w-7 text-destructive hover:text-destructive" onclick={() => remove(col)}><Trash2 class="h-3.5 w-3.5" /></Button>
            </div>
          </CardHeader>
          <CardContent>
            <p class="text-sm text-muted-foreground">{col.book_count} book{col.book_count !== 1 ? 's' : ''}</p>
          </CardContent>
        </Card>
      {/each}
    </div>
  {:else}
    <Card class="py-12 text-center">
      <CardContent>
        <Layers class="mx-auto h-12 w-12 text-muted-foreground" />
        <p class="mt-4 text-muted-foreground">No collections yet. Group related books into a universe or theme.</p>
        <Button class="mt-4" onclick={openCreate}><Plus class="mr-2 h-4 w-4" /> Create Collection</Button>
      </CardContent>
    </Card>
  {/if}
</div>

{#if showDialog}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" role="dialog" aria-modal="true">
    <div class="mx-4 w-full max-w-md rounded-lg border bg-background p-6 shadow-xl">
      <div class="mb-4 flex items-center justify-between">
        <h2 class="text-lg font-semibold">{editing ? 'Edit Collection' : 'New Collection'}</h2>
        <Button variant="ghost" size="icon" onclick={() => (showDialog = false)}><X class="h-4 w-4" /></Button>
      </div>
      <div class="space-y-4">
        <div class="space-y-1.5">
          <label class="text-sm font-medium" for="col-name">Name</label>
          <Input id="col-name" bind:value={formName} placeholder="Malazan Universe…" />
        </div>
        <div class="space-y-1.5">
          <label class="text-sm font-medium" for="col-desc">Description (optional)</label>
          <Input id="col-desc" bind:value={formDescription} placeholder="A short description…" />
        </div>
        {#if formError}<p class="text-sm text-destructive">{formError}</p>{/if}
        <div class="flex justify-end gap-2 pt-2">
          <Button variant="outline" onclick={() => (showDialog = false)} disabled={saving}>Cancel</Button>
          <Button onclick={save} disabled={saving}>{saving ? 'Saving…' : editing ? 'Save' : 'Create'}</Button>
        </div>
      </div>
    </div>
  </div>
{/if}
