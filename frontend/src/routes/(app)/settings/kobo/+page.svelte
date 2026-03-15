<script lang="ts">
  import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "$lib/components/ui/card";
  import { Button } from "$lib/components/ui/button";
  import { Badge } from "$lib/components/ui/badge";
  import { Plus, Trash2, ArrowLeft, Check, BookMarked, Pencil } from "lucide-svelte";
  import { CopyButton } from "$lib/components/ui/copy-button";
  import * as api from "$lib/api/client";
  import { getShelves } from "$lib/api/client";
  import type { KoboSyncToken } from "$lib/api/client";
  import type { Shelf } from "$lib/types/index";

  let tokens = $state<KoboSyncToken[]>([]);
  let shelves = $state<Shelf[]>([]);
  let loading = $state(true);
  let creating = $state(false);
  let newName = $state('');
  let newShelfIds = $state<Set<number>>(new Set());
  let error = $state('');

  // Per-token shelf editing
  let editingTokenId = $state<number | null>(null);
  let editShelfIds = $state<Set<number>>(new Set());
  let savingShelves = $state(false);

  async function load() {
    loading = true;
    try {
      const [t, s] = await Promise.all([api.getKoboTokens(), getShelves()]);
      tokens = t;
      shelves = s.filter(sh => !sh.is_smart);
    } catch { tokens = []; shelves = []; } finally { loading = false; }
  }

  $effect(() => { load(); });

  async function createToken() {
    creating = true;
    error = '';
    try {
      const t = await api.createKoboToken(newName.trim() || undefined, [...newShelfIds]);
      tokens = [...tokens, t];
      newName = '';
      newShelfIds = new Set();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to create token';
    } finally {
      creating = false;
    }
  }

  async function deleteToken(id: number) {
    if (!confirm('Revoke this sync token? The Kobo device using it will lose sync access.')) return;
    try {
      await api.deleteKoboToken(id);
      tokens = tokens.filter(t => t.id !== id);
      if (editingTokenId === id) editingTokenId = null;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed';
    }
  }

  function startEdit(token: KoboSyncToken) {
    editingTokenId = token.id;
    editShelfIds = new Set(token.shelves.map(s => s.id));
  }

  async function saveEdit() {
    if (editingTokenId === null) return;
    savingShelves = true;
    try {
      await api.setKoboTokenShelves(editingTokenId, [...editShelfIds]);
      tokens = tokens.map(t => {
        if (t.id !== editingTokenId) return t;
        return { ...t, shelves: shelves.filter(s => editShelfIds.has(s.id)).map(s => ({ id: s.id, name: s.name })) };
      });
      editingTokenId = null;
    } finally {
      savingShelves = false;
    }
  }

  function toggleNewShelf(id: number) {
    const next = new Set(newShelfIds);
    next.has(id) ? next.delete(id) : next.add(id);
    newShelfIds = next;
  }

  function toggleEditShelf(id: number) {
    const next = new Set(editShelfIds);
    next.has(id) ? next.delete(id) : next.add(id);
    editShelfIds = next;
  }
</script>

<div class="mx-auto max-w-2xl space-y-6 px-4 py-8 sm:px-6 lg:px-8">
  <div>
    <a href="/settings" class="mb-4 flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
      <ArrowLeft class="h-4 w-4" /> Back to Settings
    </a>
    <h1 class="text-3xl font-bold tracking-tight">Kobo Sync</h1>
    <p class="mt-1 text-muted-foreground">Sync your Kobo e-reader with Scriptorium</p>
  </div>

  <!-- Setup instructions -->
  <Card>
    <CardHeader>
      <CardTitle>Setup</CardTitle>
      <CardDescription>How to connect your Kobo device</CardDescription>
    </CardHeader>
    <CardContent class="space-y-3 text-sm text-muted-foreground">
      <ol class="list-decimal space-y-2 pl-4">
        <li>Generate a sync token below and copy the URL.</li>
        <li>Connect your Kobo to your computer via USB.</li>
        <li>Open <code class="rounded bg-muted px-1 py-0.5 text-xs">.kobo/Kobo/Kobo eReader.conf</code> on the device.</li>
        <li>Under the <code class="rounded bg-muted px-1 py-0.5 text-xs">[OneStoreServices]</code> section, set:
          <pre class="mt-1 rounded bg-muted p-2 text-xs">api_endpoint=&lt;paste your URL here&gt;</pre>
        </li>
        <li>Save the file, safely eject, and reconnect — the Kobo will sync with Scriptorium instead of the Kobo Store.</li>
      </ol>
      <p class="mt-2 text-xs">
        Each token can sync your full library or a subset of shelves. Reading progress syncs both ways.
      </p>
    </CardContent>
  </Card>

  <!-- Token management -->
  <Card>
    <CardHeader>
      <CardTitle>Sync Tokens</CardTitle>
      <CardDescription>Each token authorizes one Kobo device</CardDescription>
    </CardHeader>
    <CardContent class="space-y-4">

      <!-- Create form -->
      <div class="space-y-3 rounded-md border p-3">
        <p class="text-xs font-medium text-muted-foreground uppercase tracking-wide">New token</p>
        <div class="flex gap-2">
          <input
            bind:value={newName}
            placeholder="Device name (optional)"
            class="flex-1 rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            onkeydown={(e) => { if (e.key === 'Enter') createToken(); }}
          />
        </div>

        {#if shelves.length > 0}
          <div class="space-y-1.5">
            <p class="text-xs text-muted-foreground">
              Sync shelves <span class="italic">(leave empty to sync entire library)</span>
            </p>
            <div class="flex flex-wrap gap-1.5">
              {#each shelves as shelf}
                <button
                  class="flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs transition-colors {newShelfIds.has(shelf.id) ? 'border-foreground bg-foreground text-background' : 'border-border text-muted-foreground hover:border-foreground/40'}"
                  onclick={() => toggleNewShelf(shelf.id)}
                >
                  {#if newShelfIds.has(shelf.id)}<Check class="h-2.5 w-2.5" />{/if}
                  {shelf.name}
                </button>
              {/each}
            </div>
          </div>
        {/if}

        <Button onclick={createToken} disabled={creating} size="sm">
          <Plus class="mr-1.5 h-4 w-4" />
          {creating ? 'Creating...' : 'Generate token'}
        </Button>
      </div>

      {#if error}
        <p class="text-sm text-destructive">{error}</p>
      {/if}

      <!-- Token list -->
      {#if loading}
        <p class="text-sm text-muted-foreground">Loading tokens...</p>
      {:else if tokens.length === 0}
        <p class="text-sm text-muted-foreground">No sync tokens yet.</p>
      {:else}
        <div class="space-y-3">
          {#each tokens as token (token.id)}
            <div class="rounded-md border p-3 space-y-2">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <Badge variant={token.is_active ? 'default' : 'secondary'}>
                    {token.is_active ? 'Active' : 'Revoked'}
                  </Badge>
                  <span class="text-xs text-muted-foreground font-mono">
                    {token.token.slice(0, 8)}…
                  </span>
                </div>
                <div class="flex gap-1">
                  <CopyButton text={token.sync_url} variant="ghost" size="icon" class="h-7 w-7" />
                  <Button variant="ghost" size="icon" class="h-7 w-7 text-destructive hover:text-destructive" onclick={() => deleteToken(token.id)}>
                    <Trash2 class="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>

              <div class="text-xs text-muted-foreground truncate font-mono bg-muted rounded px-2 py-1">
                {token.sync_url}
              </div>

              <div class="flex justify-between text-xs text-muted-foreground">
                <span>Created {new Date(token.created_at).toLocaleDateString()}</span>
                {#if token.last_used}
                  <span>Last synced {new Date(token.last_used).toLocaleString()}</span>
                {/if}
              </div>

              <!-- Shelf filter -->
              {#if editingTokenId === token.id}
                <div class="space-y-2 pt-1 border-t">
                  <p class="text-xs text-muted-foreground">Select shelves to sync (empty = all books):</p>
                  <div class="flex flex-wrap gap-1.5">
                    {#each shelves as shelf}
                      <button
                        class="flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs transition-colors {editShelfIds.has(shelf.id) ? 'border-foreground bg-foreground text-background' : 'border-border text-muted-foreground hover:border-foreground/40'}"
                        onclick={() => toggleEditShelf(shelf.id)}
                      >
                        {#if editShelfIds.has(shelf.id)}<Check class="h-2.5 w-2.5" />{/if}
                        {shelf.name}
                      </button>
                    {/each}
                  </div>
                  <div class="flex gap-2">
                    <Button size="sm" onclick={saveEdit} disabled={savingShelves}>
                      {savingShelves ? 'Saving…' : 'Save'}
                    </Button>
                    <Button size="sm" variant="ghost" onclick={() => editingTokenId = null}>Cancel</Button>
                  </div>
                </div>
              {:else}
                <div class="flex items-center gap-1.5 flex-wrap pt-0.5">
                  <BookMarked class="h-3 w-3 text-muted-foreground shrink-0" />
                  {#if token.shelves.length === 0}
                    <span class="text-xs text-muted-foreground">All books</span>
                  {:else}
                    {#each token.shelves as shelf}
                      <span class="rounded-full bg-muted px-2 py-0.5 text-xs">{shelf.name}</span>
                    {/each}
                  {/if}
                  {#if shelves.length > 0}
                    <button
                      class="ml-1 text-xs text-muted-foreground hover:text-foreground"
                      onclick={() => startEdit(token)}
                      title="Edit shelves"
                    >
                      <Pencil class="h-3 w-3" />
                    </button>
                  {/if}
                </div>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    </CardContent>
  </Card>
</div>
