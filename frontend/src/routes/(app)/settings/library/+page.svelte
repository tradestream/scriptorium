<script lang="ts">
  import { Button } from "$lib/components/ui/button";
  import { Input } from "$lib/components/ui/input";
  import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "$lib/components/ui/card";
  import { Badge } from "$lib/components/ui/badge";
  import { Separator } from "$lib/components/ui/separator";
  import { Plus, RefreshCw, Trash2, Play, CheckCircle, AlertCircle, Copy, Clock, Eye, EyeOff, Users, UserPlus, UserMinus, Lock, Unlock, FileCode } from "lucide-svelte";
  import * as api from "$lib/api/client";
  import type { Library, LibraryAccess, User as UserType, IngestLog } from "$lib/types/index";
  import type { LayoutData } from '../$types';

  let { data }: { data: LayoutData } = $props();
  let user = $derived(data.user);
  let adminConfig = $derived(data.adminConfig);

  // Libraries
  let libraries = $state<Library[]>([]);
  let showCreateLibrary = $state(false);
  let newLibraryName = $state('');
  let newLibraryPath = $state('');
  let creating = $state(false);
  let createError = $state('');

  async function loadLibraries() {
    libraries = await api.getLibraries(true);
  }
  $effect(() => { loadLibraries(); });

  async function createLibrary() {
    if (!newLibraryName.trim() || !newLibraryPath.trim()) return;
    creating = true;
    createError = '';
    try {
      await api.createLibrary({ name: newLibraryName.trim(), path: newLibraryPath.trim() });
      newLibraryName = '';
      newLibraryPath = '';
      showCreateLibrary = false;
      await loadLibraries();
    } catch (err) {
      createError = err instanceof Error ? err.message : 'Failed to create library';
    } finally {
      creating = false;
    }
  }

  async function scanLibrary(id: number) {
    await api.scanLibrary(id);
  }

  async function toggleHideLibrary(lib: Library) {
    await api.updateLibrary(lib.id, { is_hidden: !lib.is_hidden });
    await loadLibraries();
  }

  async function deleteLibrary(id: number) {
    if (!confirm('Delete this library? Books will be removed from the database but not from disk.')) return;
    await api.deleteLibrary(id);
    await loadLibraries();
  }

  // Library Access Control
  let allUsers = $state<UserType[]>([]);
  let accessExpanded = $state<Record<number, boolean>>({});
  let accessGrants = $state<Record<number, LibraryAccess[]>>({});
  let accessLoading = $state<Record<number, boolean>>({});

  async function loadUsers() {
    if (!data.user?.is_admin) return;
    try { allUsers = await api.getUsers(); } catch { /* non-critical */ }
  }
  $effect(() => { loadUsers(); });

  async function toggleAccessPanel(lib: Library) {
    const open = !accessExpanded[lib.id];
    accessExpanded[lib.id] = open;
    if (open && !accessGrants[lib.id]) {
      accessLoading[lib.id] = true;
      try { accessGrants[lib.id] = await api.getLibraryAccess(lib.id); }
      catch { accessGrants[lib.id] = []; }
      finally { accessLoading[lib.id] = false; }
    }
  }

  async function grantAccess(lib: Library, userId: number) {
    await api.grantLibraryAccess(lib.id, userId);
    accessGrants[lib.id] = await api.getLibraryAccess(lib.id);
  }

  async function revokeAccess(lib: Library, userId: number) {
    await api.revokeLibraryAccess(lib.id, userId);
    accessGrants[lib.id] = await api.getLibraryAccess(lib.id);
  }

  async function revokeAllAccess(lib: Library) {
    for (const grant of accessGrants[lib.id] ?? []) {
      await api.revokeLibraryAccess(lib.id, grant.user_id);
    }
    accessGrants[lib.id] = [];
  }

  // Per-library naming pattern
  let namingExpanded = $state<Record<number, boolean>>({});
  let libNamingInput = $state<Record<number, string>>({});
  let libNamingSaving = $state<Record<number, boolean>>({});

  function toggleNamingPanel(lib: Library) {
    namingExpanded[lib.id] = !namingExpanded[lib.id];
  }

  async function saveLibraryNaming(lib: Library) {
    libNamingSaving[lib.id] = true;
    try {
      const val = libNamingInput[lib.id] ?? '';
      await api.updateLibraryNaming(lib.id, val.trim() || null);
      await loadLibraries();
    } finally {
      libNamingSaving[lib.id] = false;
    }
  }

  // Per-library exclude-patterns panel
  let excludesExpanded = $state<Record<number, boolean>>({});
  let libExcludesInput = $state<Record<number, string>>({});
  let libExcludesSaving = $state<Record<number, boolean>>({});

  function toggleExcludesPanel(lib: Library) {
    excludesExpanded[lib.id] = !excludesExpanded[lib.id];
  }

  async function saveLibraryExcludes(lib: Library) {
    libExcludesSaving[lib.id] = true;
    try {
      const raw = libExcludesInput[lib.id] ?? '';
      const patterns = raw
        .split('\n')
        .map((s) => s.trim())
        .filter((s) => s && !s.startsWith('#'));
      await api.updateLibrary(lib.id, {
        exclude_patterns: patterns.length > 0 ? patterns : null,
      });
      await loadLibraries();
    } finally {
      libExcludesSaving[lib.id] = false;
    }
  }

  // Auto-Ingest
  let ingestLogs = $state<IngestLog[]>([]);
  let ingestTotal = $state(0);
  let ingestLoading = $state(false);
  let triggering = $state(false);
  let ingestMsg = $state('');

  async function loadIngestHistory() {
    if (!data.user?.is_admin) return;
    ingestLoading = true;
    try {
      const r = await api.getIngestHistory(0, 50);
      ingestLogs = r.items;
      ingestTotal = r.total;
    } catch { /* non-critical */ } finally {
      ingestLoading = false;
    }
  }

  async function triggerIngest() {
    triggering = true;
    ingestMsg = '';
    try {
      const r = await api.triggerIngest();
      ingestMsg = r.message;
      setTimeout(() => { ingestMsg = ''; loadIngestHistory(); }, 2000);
    } catch (err) {
      ingestMsg = err instanceof Error ? err.message : 'Failed';
    } finally {
      triggering = false;
    }
  }

  $effect(() => { loadIngestHistory(); });

  // Naming pattern preview (global)
  let namingPatternInput = $state('{authors}/{title}');
  let namingPreview = $state('');
  let namingPreviewLoading = $state(false);
  let namingPreviewTimer: ReturnType<typeof setTimeout> | null = null;
  let namingEnabled = $state(false);
  let namingSaving = $state(false);
  let namingMsg = $state('');

  $effect(() => {
    if (adminConfig) {
      namingPatternInput = adminConfig.naming_pattern || '{authors}/{title}';
      namingEnabled = adminConfig.naming_enabled || false;
    }
  });

  async function fetchNamingPreview(pattern: string) {
    namingPreviewLoading = true;
    try {
      const params = new URLSearchParams({ pattern });
      const r = await fetch(`/api/v1/admin/naming/preview?${params}`, {
        headers: { Authorization: `Bearer ${api.getAuthToken()}` },
      });
      if (r.ok) {
        const d = await r.json();
        namingPreview = d.example;
      }
    } catch { /* non-critical */ } finally {
      namingPreviewLoading = false;
    }
  }

  function onNamingPatternInput(val: string) {
    namingPatternInput = val;
    if (namingPreviewTimer) clearTimeout(namingPreviewTimer);
    namingPreviewTimer = setTimeout(() => fetchNamingPreview(val), 400);
  }

  async function saveNamingSettings() {
    namingSaving = true;
    namingMsg = '';
    try {
      await api.updateNamingSettings(namingEnabled, namingPatternInput);
      namingMsg = 'Saved';
      setTimeout(() => { namingMsg = ''; }, 3000);
    } catch (e) {
      namingMsg = e instanceof Error ? e.message : 'Save failed';
    } finally {
      namingSaving = false;
    }
  }

  $effect(() => {
    if (adminConfig?.naming_pattern) fetchNamingPreview(adminConfig.naming_pattern);
  });
</script>

<!-- Libraries -->
<Card>
  <CardHeader class="flex flex-row items-center justify-between">
    <div>
      <CardTitle>Libraries</CardTitle>
      <CardDescription>Manage book libraries and their paths</CardDescription>
    </div>
    <Button size="sm" onclick={() => (showCreateLibrary = !showCreateLibrary)}>
      <Plus class="mr-2 h-4 w-4" /> Add Library
    </Button>
  </CardHeader>
  <CardContent class="space-y-3">
    {#if showCreateLibrary}
      <div class="space-y-3 rounded-md border bg-muted/50 p-4">
        <Input placeholder="Library name" bind:value={newLibraryName} />
        <Input placeholder="/path/to/books" bind:value={newLibraryPath} />
        {#if createError}
          <p class="text-sm text-destructive">{createError}</p>
        {/if}
        <div class="flex gap-2">
          <Button size="sm" onclick={createLibrary} disabled={creating}>
            {creating ? 'Creating...' : 'Create'}
          </Button>
          <Button size="sm" variant="outline" onclick={() => (showCreateLibrary = false)}>Cancel</Button>
        </div>
      </div>
    {/if}

    {#if libraries.length === 0}
      <p class="text-sm text-muted-foreground">No libraries configured yet.</p>
    {:else}
      {#each libraries as lib}
        <div class="rounded-md border">
          <div class="flex items-center justify-between p-3">
            <div>
              <p class="font-medium">{lib.name}</p>
              <p class="text-xs text-muted-foreground">{lib.path}</p>
              <div class="mt-1 flex gap-2">
                {#if lib.is_hidden}<Badge variant="secondary" class="text-xs">Hidden</Badge>{/if}
                {#if accessGrants[lib.id]?.length > 0}
                  <Badge variant="outline" class="text-xs">
                    <Lock class="mr-1 h-2.5 w-2.5" />{accessGrants[lib.id].length} user{accessGrants[lib.id].length !== 1 ? 's' : ''}
                  </Badge>
                {/if}
                {#if lib.book_count !== undefined}<span class="text-xs text-muted-foreground">{lib.book_count} books</span>{/if}
              </div>
            </div>
            <div class="flex gap-1">
              <Button variant="ghost" size="sm" onclick={() => toggleAccessPanel(lib)} class="px-2 text-xs">
                <Users class="mr-1 h-3.5 w-3.5" />Access
              </Button>
              <Button variant="ghost" size="sm" onclick={() => toggleNamingPanel(lib)} class="px-2 text-xs">
                <FileCode class="mr-1 h-3.5 w-3.5" />Pattern
              </Button>
              <Button variant="ghost" size="sm" onclick={() => toggleExcludesPanel(lib)} class="px-2 text-xs">
                <EyeOff class="mr-1 h-3.5 w-3.5" />Excludes
              </Button>
              <Button variant="ghost" size="icon" onclick={() => toggleHideLibrary(lib)} title={lib.is_hidden ? 'Show on Home/Progress' : 'Hide from Home/Progress'}>
                {#if lib.is_hidden}
                  <EyeOff class="h-4 w-4 text-muted-foreground" />
                {:else}
                  <Eye class="h-4 w-4" />
                {/if}
              </Button>
              <Button variant="ghost" size="icon" onclick={() => scanLibrary(lib.id)} title="Scan">
                <RefreshCw class="h-4 w-4" />
              </Button>
              <Button variant="ghost" size="icon" onclick={() => deleteLibrary(lib.id)} title="Delete" class="text-destructive hover:text-destructive">
                <Trash2 class="h-4 w-4" />
              </Button>
            </div>
          </div>

          {#if namingExpanded[lib.id]}
            <div class="border-t bg-muted/30 px-3 py-3 space-y-2">
              <p class="text-xs font-medium text-muted-foreground">File naming pattern</p>
              <p class="text-xs text-muted-foreground">Leave empty to use the global default.</p>
              <div class="flex gap-2">
                <input
                  type="text"
                  value={libNamingInput[lib.id] ?? lib.naming_pattern ?? ''}
                  oninput={(e) => { libNamingInput[lib.id] = (e.target as HTMLInputElement).value; }}
                  placeholder="(global default)"
                  class="flex-1 rounded-md border bg-background px-2 py-1.5 font-mono text-xs outline-none focus:ring-1 focus:ring-ring"
                />
                <Button size="sm" disabled={libNamingSaving[lib.id]} onclick={() => saveLibraryNaming(lib)}>
                  {libNamingSaving[lib.id] ? 'Saving…' : 'Save'}
                </Button>
              </div>
            </div>
          {/if}

          {#if excludesExpanded[lib.id]}
            <div class="border-t bg-muted/30 px-3 py-3 space-y-2">
              <p class="text-xs font-medium text-muted-foreground">Exclude patterns</p>
              <p class="text-xs text-muted-foreground">
                One glob per line. Combined with built-in defaults
                (<code class="text-[10px]">__MACOSX</code>,
                <code class="text-[10px]">@eaDir</code>,
                <code class="text-[10px]">*.tmp</code>,
                <code class="text-[10px]">backup/</code>, etc.) and any
                <code class="text-[10px]">.scriptoriumignore</code> file at the library root.
                <code class="text-[10px]">**/foo</code> matches at any depth;
                <code class="text-[10px]">*</code> doesn't cross directory separators.
              </p>
              <textarea
                rows="6"
                value={libExcludesInput[lib.id] ?? (lib.exclude_patterns ?? []).join('\n')}
                oninput={(e) => { libExcludesInput[lib.id] = (e.target as HTMLTextAreaElement).value; }}
                placeholder={"# Add per-library patterns here\n**/private/**\n*.bak"}
                class="w-full rounded-md border bg-background px-2 py-1.5 font-mono text-xs outline-none focus:ring-1 focus:ring-ring"
              ></textarea>
              <div class="flex justify-end">
                <Button size="sm" disabled={libExcludesSaving[lib.id]} onclick={() => saveLibraryExcludes(lib)}>
                  {libExcludesSaving[lib.id] ? 'Saving…' : 'Save'}
                </Button>
              </div>
            </div>
          {/if}

          {#if accessExpanded[lib.id]}
            <div class="border-t bg-muted/30 px-3 py-3">
              <div class="mb-2 flex items-center justify-between">
                <p class="text-xs font-medium text-muted-foreground">
                  {#if !accessGrants[lib.id]?.length}
                    <Unlock class="mr-1 inline h-3 w-3" />Open to all users
                  {:else}
                    <Lock class="mr-1 inline h-3 w-3" />Restricted — grant access per user
                  {/if}
                </p>
                {#if accessGrants[lib.id]?.length > 0}
                  <Button size="sm" variant="outline" class="h-6 px-2 text-xs" onclick={() => revokeAllAccess(lib)}>
                    <Unlock class="mr-1 h-3 w-3" />Open to all
                  </Button>
                {/if}
              </div>

              {#if accessLoading[lib.id]}
                <p class="text-xs text-muted-foreground">Loading…</p>
              {:else}
                {@const grantedUserIds = new Set((accessGrants[lib.id] ?? []).map(g => g.user_id))}
                <div class="space-y-1">
                  {#each allUsers.filter(u => u.id !== data.user?.id) as u}
                    <div class="flex items-center justify-between rounded px-1 py-0.5">
                      <span class="text-sm">{u.display_name || u.username.charAt(0).toUpperCase() + u.username.slice(1)}</span>
                      {#if grantedUserIds.has(u.id)}
                        <Button size="sm" variant="ghost" class="h-6 px-2 text-xs text-destructive hover:text-destructive" onclick={() => revokeAccess(lib, u.id)}>
                          <UserMinus class="mr-1 h-3 w-3" />Remove
                        </Button>
                      {:else}
                        <Button size="sm" variant="ghost" class="h-6 px-2 text-xs" onclick={() => grantAccess(lib, u.id)}>
                          <UserPlus class="mr-1 h-3 w-3" />Grant
                        </Button>
                      {/if}
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
          {/if}
        </div>
      {/each}
    {/if}
  </CardContent>
</Card>

<!-- Auto-Ingest -->
{#if user?.is_admin}
  <Card>
    <CardHeader class="flex flex-row items-center justify-between">
      <div>
        <CardTitle>Auto-Ingest</CardTitle>
        <CardDescription>Books dropped in the ingest folder are automatically imported</CardDescription>
      </div>
      <Button size="sm" variant="outline" onclick={triggerIngest} disabled={triggering}>
        <Play class="mr-2 h-4 w-4" />
        {triggering ? 'Queuing...' : 'Trigger Scan'}
      </Button>
    </CardHeader>
    <CardContent class="space-y-4">
      <p class="text-sm text-muted-foreground">
        Configure the ingest folder via <code class="rounded bg-muted px-1 py-0.5 text-xs">INGEST_PATH</code>.
        Drop supported ebook files there and they will be automatically detected and imported.
      </p>
      {#if ingestMsg}
        <p class="text-sm text-green-600">{ingestMsg}</p>
      {/if}

      <!-- Ingest history -->
      <Separator />
      <div class="flex items-center justify-between">
        <p class="text-sm font-medium">Recent Ingest History</p>
        <span class="text-xs text-muted-foreground">{ingestTotal} total</span>
      </div>

      {#if ingestLoading}
        <div class="space-y-2">
          {#each [1,2,3] as _}
            <div class="h-8 animate-pulse rounded bg-muted"></div>
          {/each}
        </div>
      {:else if ingestLogs.length === 0}
        <p class="text-sm text-muted-foreground">No ingest activity yet.</p>
      {:else}
        <div class="overflow-hidden rounded-md border">
          <table class="w-full text-sm">
            <thead class="bg-muted/50">
              <tr>
                <th class="px-3 py-2 text-left font-medium text-muted-foreground">File</th>
                <th class="px-3 py-2 text-left font-medium text-muted-foreground">Status</th>
                <th class="px-3 py-2 text-left font-medium text-muted-foreground">Date</th>
              </tr>
            </thead>
            <tbody class="divide-y">
              {#each ingestLogs as log}
                <tr class="hover:bg-muted/30">
                  <td class="max-w-xs truncate px-3 py-2">
                    <span title={log.filename}>{log.filename.split('/').at(-1)}</span>
                    {#if log.error_message}
                      <p class="truncate text-xs text-destructive" title={log.error_message}>{log.error_message}</p>
                    {/if}
                  </td>
                  <td class="px-3 py-2">
                    {#if log.status === 'imported'}
                      <span class="flex items-center gap-1 text-green-600">
                        <CheckCircle class="h-3.5 w-3.5" /> Imported
                      </span>
                    {:else if log.status === 'duplicate'}
                      <span class="flex items-center gap-1 text-muted-foreground">
                        <Copy class="h-3.5 w-3.5" /> Duplicate
                      </span>
                    {:else if log.status === 'error'}
                      <span class="flex items-center gap-1 text-destructive">
                        <AlertCircle class="h-3.5 w-3.5" /> Error
                      </span>
                    {:else}
                      <span class="flex items-center gap-1 text-muted-foreground">
                        <Clock class="h-3.5 w-3.5" /> {log.status}
                      </span>
                    {/if}
                  </td>
                  <td class="whitespace-nowrap px-3 py-2 text-xs text-muted-foreground">
                    {new Date(log.created_at).toLocaleString()}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </CardContent>
  </Card>
{/if}

<!-- File Naming Pattern -->
{#if user?.is_admin && adminConfig}
  <Card>
    <CardHeader>
      <CardTitle>File Naming Pattern</CardTitle>
      <CardDescription>How book files are named and organized when imported into a library</CardDescription>
    </CardHeader>
    <CardContent class="space-y-4">

      <!-- Enable/disable toggle -->
      <div class="flex items-center gap-3">
        <label class="flex items-center gap-2 cursor-pointer select-none">
          <input
            type="checkbox"
            bind:checked={namingEnabled}
            class="h-4 w-4 rounded border accent-primary"
          />
          <span class="text-sm font-medium">Enable file naming pattern</span>
        </label>
        {#if namingEnabled}
          <span class="text-xs text-green-600 font-medium">Active</span>
        {:else}
          <span class="text-xs text-muted-foreground">Files placed flat in library root</span>
        {/if}
      </div>

      <!-- Pattern input + live preview -->
      <div class="space-y-2">
        <label class="text-xs font-medium text-muted-foreground">Pattern</label>
        <input
          type="text"
          value={namingPatternInput}
          oninput={(e) => onNamingPatternInput((e.target as HTMLInputElement).value)}
          class="w-full rounded-md border bg-background px-3 py-2 font-mono text-sm outline-none focus:ring-1 focus:ring-ring"
          placeholder="{'{authors}/{title}'}"
        />
        {#if namingPreview}
          <div class="flex items-center gap-2 rounded-md bg-muted/50 px-3 py-2 text-xs">
            <span class="text-muted-foreground shrink-0">Example:</span>
            <code class="break-all text-foreground">{namingPreview}</code>
            {#if namingPreviewLoading}<span class="text-muted-foreground/50">…</span>{/if}
          </div>
        {/if}
      </div>

      <!-- Token reference -->
      <div class="space-y-1.5">
        <p class="text-xs font-medium text-muted-foreground">Available placeholders</p>
        <div class="grid grid-cols-2 gap-x-6 gap-y-1 text-xs">
          {#each [
            ['{title}', 'Book title'],
            ['{author}', 'First author'],
            ['{authors}', 'All authors, comma-separated'],
            ['{year}', 'Publication year'],
            ['{series}', 'Series name'],
            ['{series_index}', 'Series position (01, 02 …)'],
            ['{publisher}', 'Publisher'],
            ['{language}', 'Language code (en, fr …)'],
            ['{isbn}', 'ISBN'],
          ] as [token, desc]}
            <div class="flex items-baseline gap-1.5">
              <code class="rounded bg-muted px-1 font-mono text-[11px] shrink-0">{token}</code>
              <span class="text-muted-foreground truncate">{desc}</span>
            </div>
          {/each}
        </div>
        <p class="pt-1 text-xs text-muted-foreground">
          Wrap any section in <code class="rounded bg-muted px-1 font-mono">&lt; &gt;</code> to make it optional — the block is omitted entirely if any placeholder inside it is empty.<br />
          Example: <code class="rounded bg-muted px-1 font-mono text-[11px]">{'{authors}/<{series}/{series_index}. >{title}'}</code>
        </p>
      </div>

      <!-- Save -->
      <div class="flex items-center gap-3">
        <Button size="sm" onclick={saveNamingSettings} disabled={namingSaving}>
          {namingSaving ? 'Saving…' : 'Save'}
        </Button>
        {#if namingMsg}
          <span class="text-xs {namingMsg === 'Saved' ? 'text-green-600' : 'text-destructive'}">{namingMsg}</span>
        {/if}
      </div>

    </CardContent>
  </Card>
{/if}

<!-- Loose Leaves -->
{#if user?.is_admin && adminConfig}
  <Card>
    <CardHeader>
      <CardTitle>Loose Leaves</CardTitle>
      <CardDescription>Staged review queue — drop files here before importing to a library</CardDescription>
    </CardHeader>
    <CardContent class="space-y-3">
      <div class="grid grid-cols-2 gap-3 text-sm">
        <div>
          <p class="text-xs text-muted-foreground">Loose Leaves Path</p>
          <code class="text-xs">{adminConfig.loose_leaves_path}</code>
        </div>
      </div>
      <p class="text-sm text-muted-foreground">
        Files placed in the Loose Leaves folder appear in <a href="/loose-leaves" class="underline hover:text-foreground">the review queue</a> where you can preview enriched metadata and import or reject each file.
      </p>
      <p class="text-xs text-muted-foreground">
        Override with <code class="rounded bg-muted px-1">LOOSE_LEAVES_PATH</code> in your <code class="rounded bg-muted px-1">.env</code> file.
      </p>
    </CardContent>
  </Card>
{/if}
