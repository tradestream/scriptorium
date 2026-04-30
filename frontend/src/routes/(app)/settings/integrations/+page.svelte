<script lang="ts">
  import { Button } from "$lib/components/ui/button";
  import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "$lib/components/ui/card";
  import { Badge } from "$lib/components/ui/badge";
  import { Separator } from "$lib/components/ui/separator";
  import { RefreshCw, CheckCircle, AlertCircle, Download, Headphones, Link2 } from "lucide-svelte";
  import * as api from "$lib/api/client";
  import type { Library } from "$lib/types/index";
  import type { LayoutData } from '../$types';

  let { data }: { data: LayoutData } = $props();
  let user = $derived(data.user);

  // Need libraries list for ABS import dropdown
  let libraries = $state<Library[]>([]);
  $effect(() => {
    api.getLibraries(true).then((libs) => { libraries = libs; }).catch(() => {});
  });

  // Kobo compatibility health
  let koboHealth = $state<import('$lib/api/client').KoboHealth | null>(null);
  let koboHealthLoading = $state(false);
  let koboHealthError = $state('');

  async function loadKoboHealth() {
    koboHealthLoading = true;
    koboHealthError = '';
    try {
      koboHealth = await api.getKoboHealth();
    } catch (e) {
      koboHealthError = e instanceof Error ? e.message : 'Failed to load Kobo health';
    } finally {
      koboHealthLoading = false;
    }
  }

  $effect(() => {
    if (data.user?.is_admin && koboHealth === null && !koboHealthLoading) {
      loadKoboHealth();
    }
  });

  // Kobo Fonts (USB sideload bundle)
  let koboFonts = $state<import('$lib/api/client').KoboFontsListing | null>(null);
  let koboFontsLoading = $state(false);
  let koboFontsError = $state('');

  async function loadKoboFonts() {
    koboFontsLoading = true;
    koboFontsError = '';
    try {
      koboFonts = await api.listKoboFonts();
    } catch (e) {
      koboFontsError = e instanceof Error ? e.message : 'Failed to load fonts';
    } finally {
      koboFontsLoading = false;
    }
  }

  $effect(() => {
    if (data.user?.is_admin && koboFonts === null && !koboFontsLoading) {
      loadKoboFonts();
    }
  });

  function formatMB(bytes: number): string {
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  // AudiobookShelf
  let absStatus = $state<import('$lib/api/client').AbsStatus | null>(null);
  let absLibraries = $state<import('$lib/api/client').AbsLibrary[]>([]);
  let absLibrariesLoaded = $state(false);
  let absSyncing = $state(false);
  let absSyncingCovers = $state(false);
  let absImporting = $state(false);
  let absMsg = $state('');
  let absMsgOk = $state(true);
  let selectedAbsLibraryId = $state('');
  let selectedScriptoriumLibraryId = $state(0);

  async function loadAbsStatus() {
    try {
      absStatus = await api.getAbsStatus();
    } catch { /* non-critical */ }
  }

  $effect(() => {
    if (data.user?.is_admin) loadAbsStatus();
  });

  async function loadAbsLibraries() {
    absLibrariesLoaded = false;
    try {
      absLibraries = await api.getAbsLibraries();
      if (absLibraries.length) selectedAbsLibraryId = absLibraries[0].id;
    } catch (e) {
      absMsg = e instanceof Error ? e.message : 'Failed to load libraries';
      absMsgOk = false;
    } finally {
      absLibrariesLoaded = true;
    }
  }

  async function syncAbsProgress() {
    absSyncing = true;
    absMsg = '';
    try {
      const r = await api.syncAbsProgress();
      absMsg = `Synced: ${r.updated} updated, ${r.matched} matched, ${r.skipped_unlinked} unlinked`;
      absMsgOk = true;
    } catch (e) {
      absMsg = e instanceof Error ? e.message : 'Sync failed';
      absMsgOk = false;
    } finally {
      absSyncing = false;
    }
  }

  async function syncAbsCovers() {
    absSyncingCovers = true;
    absMsg = '';
    try {
      const { job_id, total } = await api.syncAbsCovers();
      absMsg = `Syncing covers… 0/${total}`;
      absMsgOk = true;
      const poll = setInterval(async () => {
        try {
          const job = await api.getAbsCoverSyncJob(job_id);
          absMsg = `Syncing covers… ${job.done}/${job.total}`;
          if (job.status === 'completed' || job.status === 'cancelled' || job.status === 'failed') {
            clearInterval(poll);
            absMsg = `Covers synced: ${job.done - job.failed} updated, ${job.failed} failed`;
            absSyncingCovers = false;
          }
        } catch {
          clearInterval(poll);
          absSyncingCovers = false;
        }
      }, 2000);
    } catch (e) {
      absMsg = e instanceof Error ? e.message : 'Cover sync failed';
      absMsgOk = false;
      absSyncingCovers = false;
    }
  }

  async function importFromAbs() {
    if (!selectedAbsLibraryId || !selectedScriptoriumLibraryId) return;
    absImporting = true;
    absMsg = '';
    try {
      const r = await api.importFromAbs(selectedAbsLibraryId, selectedScriptoriumLibraryId);
      absMsg = `Import done: ${r.created} new books, ${r.linked} linked, ${r.skipped_already_linked} already linked`;
      absMsgOk = true;
    } catch (e) {
      absMsg = e instanceof Error ? e.message : 'Import failed';
      absMsgOk = false;
    } finally {
      absImporting = false;
    }
  }
</script>

<!-- AudiobookShelf -->
{#if user?.is_admin}
  <Card>
    <CardHeader>
      <CardTitle class="flex items-center gap-2">
        <Headphones class="h-4 w-4" /> AudiobookShelf
      </CardTitle>
      <CardDescription>Connect to your self-hosted AudiobookShelf instance to sync listening progress and import audiobooks</CardDescription>
    </CardHeader>
    <CardContent class="space-y-4">

      <!-- Connection status -->
      {#if absStatus}
        <div class="flex items-center gap-2 text-sm">
          {#if absStatus.connected}
            <CheckCircle class="h-3.5 w-3.5 text-green-500 shrink-0" />
            <span class="font-medium text-green-700 dark:text-green-400">Connected</span>
            {#if absStatus.abs_user}
              <span class="text-muted-foreground">as <strong>{absStatus.abs_user}</strong></span>
            {/if}
            {#if absStatus.server_url}
              <code class="ml-auto text-xs text-muted-foreground">{absStatus.server_url}</code>
            {/if}
          {:else if absStatus.configured}
            <AlertCircle class="h-3.5 w-3.5 text-destructive shrink-0" />
            <span class="text-destructive font-medium">Cannot connect</span>
            {#if absStatus.error}<span class="text-xs text-muted-foreground">— {absStatus.error}</span>{/if}
          {:else}
            <AlertCircle class="h-3.5 w-3.5 text-muted-foreground/50 shrink-0" />
            <span class="text-muted-foreground">Not configured</span>
          {/if}
        </div>
      {/if}

      {#if absStatus?.connected}
        <!-- Sync progress -->
        <div class="space-y-2">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm font-medium">Sync Listening Progress</p>
              <p class="text-xs text-muted-foreground">Pull your ABS listening progress into Scriptorium reading status</p>
            </div>
            <Button size="sm" variant="outline" onclick={syncAbsProgress} disabled={absSyncing}>
              <RefreshCw class="mr-1.5 h-3.5 w-3.5 {absSyncing ? 'animate-spin' : ''}" />
              {absSyncing ? 'Syncing…' : 'Sync Now'}
            </Button>
          </div>
          <p class="text-xs text-muted-foreground">
            Books must be linked to an ABS item — use <strong>Import</strong> below or the link button on individual book pages.
          </p>
        </div>

        <Separator />

        <!-- Sync covers -->
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm font-medium">Sync Covers from ABS</p>
            <p class="text-xs text-muted-foreground">Download cover images from ABS for linked books that don't have one</p>
          </div>
          <Button size="sm" variant="outline" onclick={syncAbsCovers} disabled={absSyncingCovers}>
            <RefreshCw class="mr-1.5 h-3.5 w-3.5 {absSyncingCovers ? 'animate-spin' : ''}" />
            {absSyncingCovers ? 'Syncing…' : 'Sync Covers'}
          </Button>
        </div>

        <Separator />

        <!-- Import library -->
        <div class="space-y-3">
          <p class="text-sm font-medium">Import ABS Library</p>
          <p class="text-xs text-muted-foreground">
            Import audiobooks from an ABS library into a Scriptorium library.
            Existing books are matched by ISBN or title+author and linked; new books are created as stubs.
          </p>

          {#if !absLibrariesLoaded}
            <Button size="sm" variant="outline" onclick={loadAbsLibraries}>
              Load ABS Libraries
            </Button>
          {:else}
            <div class="flex flex-wrap gap-2 items-end">
              <div class="space-y-1">
                <label class="text-xs text-muted-foreground">ABS Library</label>
                <select
                  bind:value={selectedAbsLibraryId}
                  class="rounded-md border bg-background px-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-ring min-w-36"
                >
                  {#each absLibraries as lib}
                    <option value={lib.id}>{lib.name}</option>
                  {/each}
                </select>
              </div>
              <div class="space-y-1">
                <label class="text-xs text-muted-foreground">Into Library</label>
                <select
                  bind:value={selectedScriptoriumLibraryId}
                  class="rounded-md border bg-background px-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-ring min-w-36"
                >
                  <option value={0} disabled>Select…</option>
                  {#each libraries as lib}
                    <option value={lib.id}>{lib.name}</option>
                  {/each}
                </select>
              </div>
              <Button
                size="sm"
                onclick={importFromAbs}
                disabled={absImporting || !selectedAbsLibraryId || !selectedScriptoriumLibraryId}
              >
                <Link2 class="mr-1.5 h-3.5 w-3.5" />
                {absImporting ? 'Importing…' : 'Import'}
              </Button>
            </div>
          {/if}
        </div>
      {/if}

      {#if absMsg}
        <p class="text-sm {absMsgOk ? 'text-green-600 dark:text-green-400' : 'text-destructive'}">{absMsg}</p>
      {/if}

      <!-- Setup instructions (only shown when not configured) -->
      {#if !absStatus?.configured}
        <div class="rounded-md border border-dashed p-4 space-y-2 text-sm">
          <p class="font-medium">How to connect</p>
          <ol class="space-y-2 text-muted-foreground list-none">
            <li class="flex gap-2.5">
              <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold">1</span>
              In AudiobookShelf, go to <strong class="text-foreground">your profile icon → API Keys</strong> and create a new key.
            </li>
            <li class="flex gap-2.5">
              <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold">2</span>
              Add to your <code class="rounded bg-muted px-1 font-mono text-xs">backend/.env</code>:
              <code class="block mt-1 rounded bg-muted px-3 py-2 font-mono text-xs">ABS_URL=http://192.168.1.10:13378<br />ABS_API_KEY=your-key-here</code>
            </li>
            <li class="flex gap-2.5">
              <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold">3</span>
              Restart the backend container and reload this page.
            </li>
          </ol>
        </div>
      {/if}

    </CardContent>
  </Card>
{/if}

<!-- Kobo Compatibility Health -->
{#if user?.is_admin}
  <Card>
    <CardHeader>
      <CardTitle>Kobo Compatibility</CardTitle>
      <CardDescription>kepubify, EPUBCheck, fixed-layout count, and KEPUB cache coverage</CardDescription>
    </CardHeader>
    <CardContent class="space-y-4">
      {#if koboHealthLoading && !koboHealth}
        <p class="text-sm text-muted-foreground">Checking…</p>
      {:else if koboHealthError}
        <p class="text-sm text-destructive">{koboHealthError}</p>
      {:else if koboHealth}
        <!-- kepubify status -->
        <div class="flex items-start gap-3 rounded-md border bg-muted/30 px-3 py-2 text-sm">
          {#if koboHealth.kepubify.available}
            <CheckCircle class="mt-0.5 h-4 w-4 shrink-0 text-green-500" />
            <div class="min-w-0 flex-1">
              <p class="font-medium">kepubify {koboHealth.kepubify.version ?? 'installed'}</p>
              <p class="break-all text-xs text-muted-foreground">{koboHealth.kepubify.path}</p>
            </div>
          {:else}
            <AlertCircle class="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
            <div class="min-w-0 flex-1">
              <p class="font-medium">kepubify not installed</p>
              <p class="text-xs text-muted-foreground">
                Sync serves the raw EPUB. Install kepubify or set <code class="rounded bg-muted px-1 py-0.5">KEPUBIFY_PATH</code>
                to enable real KEPUB conversion + reading-position spans.
              </p>
            </div>
          {/if}
        </div>

        <!-- EPUBCheck status (informational only) -->
        <div class="flex items-start gap-3 rounded-md border bg-muted/30 px-3 py-2 text-sm">
          {#if koboHealth.epubcheck.available}
            <CheckCircle class="mt-0.5 h-4 w-4 shrink-0 text-green-500" />
            <div class="min-w-0 flex-1">
              <p class="font-medium">EPUBCheck available</p>
              <p class="break-all text-xs text-muted-foreground">{koboHealth.epubcheck.path}</p>
            </div>
          {:else}
            <AlertCircle class="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
            <div class="min-w-0 flex-1">
              <p class="font-medium">EPUBCheck not on PATH</p>
              <p class="text-xs text-muted-foreground">
                Optional. Install if you want to validate generated EPUBs (analysis exports, study editions, comic conversions) against IDPF spec.
              </p>
            </div>
          {/if}
        </div>

        <!-- Library coverage -->
        <div class="grid gap-3 rounded-md border bg-muted/30 p-3 text-sm sm:grid-cols-4">
          <div>
            <p class="text-xs text-muted-foreground">EPUBs total</p>
            <p class="font-medium">{koboHealth.library.total_epubs}</p>
          </div>
          <div>
            <p class="text-xs text-muted-foreground">Fixed-layout</p>
            <p class="font-medium">{koboHealth.library.fixed_layout_count}</p>
          </div>
          <div>
            <p class="text-xs text-muted-foreground">KEPUB cached</p>
            <p class="font-medium">{koboHealth.library.kepub_cached_count} / {koboHealth.library.kepub_eligible_count}</p>
          </div>
          <div>
            <p class="text-xs text-muted-foreground">Coverage</p>
            <p class="font-medium {koboHealth.library.coverage_percent >= 95 ? 'text-green-600 dark:text-green-400' : koboHealth.library.coverage_percent >= 50 ? 'text-amber-600 dark:text-amber-400' : 'text-destructive'}">
              {koboHealth.library.coverage_percent}%
            </p>
          </div>
        </div>

        <!-- Auto-convert + backfill flags -->
        <div class="flex flex-wrap gap-2 text-xs">
          <Badge variant={koboHealth.auto_convert_enabled ? 'secondary' : 'outline'}>
            Auto-convert on import: {koboHealth.auto_convert_enabled ? 'on' : 'off'}
          </Badge>
          <Badge variant={koboHealth.backfill_done ? 'secondary' : 'outline'}>
            Initial backfill: {koboHealth.backfill_done ? 'done' : 'pending'}
          </Badge>
        </div>

        <Button variant="outline" size="sm" onclick={loadKoboHealth} disabled={koboHealthLoading}>
          <RefreshCw class="mr-2 h-3.5 w-3.5" /> Recheck
        </Button>
      {/if}
    </CardContent>
  </Card>
{/if}

<!-- Kobo Fonts (USB sideload) -->
{#if user?.is_admin}
  <Card>
    <CardHeader>
      <CardTitle>Kobo Fonts</CardTitle>
      <CardDescription>Curated TTF/OTF bundle for the device's <code class="rounded bg-muted px-1 py-0.5 text-xs">.fonts/</code> folder</CardDescription>
    </CardHeader>
    <CardContent class="space-y-4">
      <p class="text-sm text-muted-foreground">
        Stock Kobos don't accept fonts over the sync API. Plug your Kobo in via USB,
        download the bundle, and unzip it into the device's <code class="rounded bg-muted px-1 py-0.5">.fonts/</code> folder
        (create the folder if it doesn't exist). Eject and reboot — the new families appear in <em>Reading Settings → Font</em>.
      </p>

      {#if koboFontsLoading && !koboFonts}
        <p class="text-sm text-muted-foreground">Scanning fonts directory…</p>
      {:else if koboFonts && !koboFonts.available}
        <div class="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm dark:border-amber-800 dark:bg-amber-950/30">
          <AlertCircle class="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
          <div>
            <p class="font-medium">Fonts directory not found</p>
            <p class="text-xs text-muted-foreground">
              Set <code class="rounded bg-muted px-1 py-0.5">KOBO_FONTS_PATH</code> to a folder of TTF/OTF files. Currently looking at:
              <code class="break-all">{koboFonts.path}</code>
            </p>
          </div>
        </div>
      {:else if koboFonts}
        <div class="grid gap-2 rounded-md border bg-muted/30 p-3 text-sm sm:grid-cols-3">
          <div>
            <p class="text-xs text-muted-foreground">Families</p>
            <p class="font-medium">{koboFonts.families.length}</p>
          </div>
          <div>
            <p class="text-xs text-muted-foreground">Files</p>
            <p class="font-medium">{koboFonts.total_files}</p>
          </div>
          <div>
            <p class="text-xs text-muted-foreground">Bundle size</p>
            <p class="font-medium">{formatMB(koboFonts.total_bytes)}</p>
          </div>
        </div>

        {#if koboFonts.families.length > 0}
          <details class="rounded border">
            <summary class="cursor-pointer px-3 py-2 text-sm font-medium hover:bg-muted/50">
              View families ({koboFonts.families.length})
            </summary>
            <div class="border-t px-3 py-2">
              <ul class="grid gap-1 text-xs sm:grid-cols-2">
                {#each koboFonts.families as fam}
                  <li class="flex items-baseline justify-between gap-2">
                    <span class="font-medium">{fam.family}</span>
                    <span class="text-muted-foreground">{fam.styles.length} {fam.styles.length === 1 ? 'style' : 'styles'}</span>
                  </li>
                {/each}
              </ul>
            </div>
          </details>
        {/if}
      {/if}

      {#if koboFontsError}
        <p class="text-sm text-destructive">{koboFontsError}</p>
      {/if}

      <Button
        href={api.koboFontsBundleUrl()}
        download
        class="w-full"
        disabled={!koboFonts?.available || koboFonts.total_files === 0}
      >
        <Download class="mr-2 h-4 w-4" />
        Download fonts bundle
      </Button>
    </CardContent>
  </Card>
{/if}

<!-- OPDS / Device Sync -->
<Card>
  <CardHeader>
    <CardTitle>Device Sync</CardTitle>
    <CardDescription>OPDS, Kobo, and KOReader sync settings</CardDescription>
  </CardHeader>
  <CardContent class="space-y-4">
    <div class="space-y-1">
      <p class="text-sm font-medium">OPDS Catalog</p>
      <p class="text-sm text-muted-foreground">
        Compatible with Moon+ Reader, Kybook, Panels, and other OPDS clients.
      </p>
      <code class="block rounded bg-muted px-2 py-1 text-xs">/opds/catalog</code>
    </div>
    <Separator />
    <div class="flex items-center justify-between">
      <div class="space-y-0.5">
        <p class="text-sm font-medium">Kobo e-Reader Sync</p>
        <p class="text-sm text-muted-foreground">Generate a token to sync with your Kobo device.</p>
      </div>
      <Button variant="outline" size="sm" href="/settings/kobo">Manage Tokens</Button>
    </div>
    <Separator />
    <div class="space-y-1">
      <p class="text-sm font-medium">KOReader Progress Sync</p>
      <p class="text-sm text-muted-foreground">
        In KOReader → Settings → Progress Sync, set the server to:
      </p>
      <code class="block rounded bg-muted px-2 py-1 text-xs">/api/ko</code>
      <p class="text-xs text-muted-foreground">Use your Scriptorium username and password to authenticate.</p>
    </div>
  </CardContent>
</Card>
