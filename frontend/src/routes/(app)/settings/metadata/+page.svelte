<script lang="ts">
  import { Button } from "$lib/components/ui/button";
  import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "$lib/components/ui/card";
  import { CheckCircle, AlertCircle, Key, Sparkles, X, FileText } from "lucide-svelte";
  import * as api from "$lib/api/client";
  import type { Library } from "$lib/types/index";
  import type { LayoutData } from '../$types';

  let { data }: { data: LayoutData } = $props();
  let user = $derived(data.user);
  let adminConfig = $state(data.adminConfig);

  // Need libraries list for the bulk-enrichment library filter dropdown
  let libraries = $state<Library[]>([]);
  $effect(() => {
    if (user?.is_admin) {
      api.getLibraries(true).then((libs) => { libraries = libs; }).catch(() => {});
    }
  });

  // Enrichment keys
  let enrichmentExpanded = $state<Record<string, boolean>>({});
  let enrichmentInput = $state<Record<string, string>>({});
  let enrichmentSaving = $state(false);
  let enrichmentMsg = $state('');
  let enrichmentMsgOk = $state(true);

  function toggleEnrichmentEdit(key: string) {
    enrichmentExpanded[key] = !enrichmentExpanded[key];
    if (enrichmentExpanded[key]) enrichmentInput[key] = '';
  }

  async function saveEnrichmentKey(key: string) {
    enrichmentSaving = true;
    enrichmentMsg = '';
    try {
      await api.updateEnrichmentKeys({ [key]: enrichmentInput[key] ?? '' });
      adminConfig = await api.getAdminConfig();
      enrichmentExpanded[key] = false;
      enrichmentInput[key] = '';
      enrichmentMsg = 'Saved';
      enrichmentMsgOk = true;
      setTimeout(() => { enrichmentMsg = ''; }, 3000);
    } catch (e) {
      enrichmentMsg = e instanceof Error ? e.message : 'Save failed';
      enrichmentMsgOk = false;
    } finally {
      enrichmentSaving = false;
    }
  }

  // Bulk Enrichment
  let bulkLibraryId = $state<number | null>(null);
  let bulkMissingCover = $state(true);
  let bulkMissingDescription = $state(true);
  let bulkMissingAuthors = $state(false);
  let bulkForce = $state(false);
  let bulkProvider = $state('');
  let bulkJob = $state<import('$lib/api/client').BulkEnrichJob | null>(null);
  let bulkStarting = $state(false);
  let bulkMsg = $state('');
  let bulkMsgOk = $state(true);
  let _bulkPollTimer: ReturnType<typeof setInterval> | null = null;

  function _stopBulkPoll() {
    if (_bulkPollTimer) { clearInterval(_bulkPollTimer); _bulkPollTimer = null; }
  }

  async function _pollBulkJob(jobId: string) {
    try {
      bulkJob = await api.getBulkEnrichJob(jobId);
      if (bulkJob.status === 'done' || bulkJob.status === 'cancelled' || bulkJob.status === 'error') {
        _stopBulkPoll();
        bulkMsg = bulkJob.status === 'done'
          ? `Done — ${bulkJob.done - bulkJob.failed} enriched, ${bulkJob.failed} failed`
          : bulkJob.status === 'cancelled' ? 'Cancelled' : `Error: ${bulkJob.error ?? 'unknown'}`;
        bulkMsgOk = bulkJob.status === 'done';
      }
    } catch { _stopBulkPoll(); }
  }

  async function startBulkEnrich() {
    bulkStarting = true;
    bulkMsg = '';
    bulkJob = null;
    _stopBulkPoll();
    try {
      const hasFilter = bulkMissingCover || bulkMissingDescription || bulkMissingAuthors || bulkLibraryId;
      if (!hasFilter && !bulkForce) {
        bulkMsg = 'Select at least one filter or enable Force to run';
        bulkMsgOk = false;
        return;
      }
      const r = await api.startBulkEnrich({
        library_id: bulkLibraryId,
        missing_cover: bulkMissingCover,
        missing_description: bulkMissingDescription,
        missing_authors: bulkMissingAuthors,
        force: bulkForce,
        provider: bulkProvider || null,
      });
      bulkMsg = `Job started — ${r.total} books to process`;
      bulkMsgOk = true;
      bulkJob = { job_id: r.job_id, status: 'queued', total: r.total, done: 0, failed: 0, current: '', started_at: new Date().toISOString(), error: null };
      _bulkPollTimer = setInterval(() => _pollBulkJob(r.job_id), 2000);
    } catch (e) {
      bulkMsg = e instanceof Error ? e.message : 'Failed to start';
      bulkMsgOk = false;
    } finally {
      bulkStarting = false;
    }
  }

  async function cancelBulkEnrich() {
    if (!bulkJob) return;
    await api.cancelBulkEnrichJob(bulkJob.job_id);
    _stopBulkPoll();
    bulkMsg = 'Cancellation requested…';
    bulkMsgOk = true;
  }

  // Bulk Identifier Extraction
  let idJob = $state<{ job_id: string; status: string; total: number; done: number; found_isbn: number; found_doi: number; failed: number } | null>(null);
  let idStarting = $state(false);
  let idMsg = $state('');
  let idMsgOk = $state(true);
  let _idPollTimer: ReturnType<typeof setInterval> | null = null;

  function _stopIdPoll() {
    if (_idPollTimer) { clearInterval(_idPollTimer); _idPollTimer = null; }
  }

  async function _pollIdJob(jobId: string) {
    try {
      idJob = await api.getBulkIdentifiersJob(jobId);
      if (idJob.status === 'done' || idJob.status === 'cancelled') {
        _stopIdPoll();
        idMsg = `Done — ${idJob.found_isbn} ISBNs, ${idJob.found_doi} DOIs found · ${idJob.failed} failed`;
        idMsgOk = true;
      }
    } catch { _stopIdPoll(); }
  }

  async function startBulkIdentifiers() {
    idStarting = true;
    idMsg = '';
    idJob = null;
    _stopIdPoll();
    try {
      const r = await api.startBulkIdentifiers();
      idMsg = `Job started — ${r.total} books to scan`;
      idMsgOk = true;
      idJob = { job_id: r.job_id, status: 'queued', total: r.total, done: 0, found_isbn: 0, found_doi: 0, failed: 0 };
      _idPollTimer = setInterval(() => _pollIdJob(r.job_id), 2000);
    } catch (e) {
      idMsg = e instanceof Error ? e.message : 'Failed to start';
      idMsgOk = false;
    } finally {
      idStarting = false;
    }
  }

  // Filename Metadata Extraction
  let fnJob = $state<any>(null);
  let fnStarting = $state(false);
  let fnMsg = $state('');
  let _fnPoll: ReturnType<typeof setInterval> | null = null;

  async function startFilenameExtract() {
    fnStarting = true;
    fnMsg = '';
    fnJob = null;
    try {
      const r = await api.startFilenameExtract();
      fnMsg = `Processing ${r.total} books…`;
      fnJob = { ...r, status: 'queued', done: 0, applied: 0, skipped: 0, failed: 0 };
      _fnPoll = setInterval(async () => {
        try {
          fnJob = await api.getFilenameExtractJob(r.job_id);
          fnMsg = `Extracting… ${fnJob.done}/${fnJob.total} (${fnJob.applied} applied)`;
          if (fnJob.status === 'done' || fnJob.status === 'cancelled') {
            clearInterval(_fnPoll!);
            fnMsg = `Done — ${fnJob.applied} updated, ${fnJob.skipped} skipped, ${fnJob.failed} failed`;
            fnStarting = false;
          }
        } catch { clearInterval(_fnPoll!); fnStarting = false; }
      }, 2000);
    } catch (e) {
      fnMsg = e instanceof Error ? e.message : 'Failed';
      fnStarting = false;
    }
  }

  // Reconnect to active background jobs on page load
  $effect(() => {
    if (!data.user?.is_admin) return;
    api.getActiveBulkEnrichJob().then((job) => {
      if (job && (job.status === 'running' || job.status === 'queued')) {
        bulkJob = job;
        bulkMsg = `Reconnected — ${job.done}/${job.total} processed`;
        bulkMsgOk = true;
        _bulkPollTimer = setInterval(() => _pollBulkJob(job.job_id), 2000);
      }
    }).catch(() => {});
    api.getActiveBulkIdentifiersJob().then((job) => {
      if (job && (job.status === 'running' || job.status === 'queued')) {
        idJob = job;
        idMsg = `Reconnected — ${job.done}/${job.total} scanned`;
        idMsgOk = true;
        _idPollTimer = setInterval(() => _pollIdJob(job.job_id), 2000);
      }
    }).catch(() => {});
  });
</script>

<!-- Metadata Enrichment -->
{#if user?.is_admin && adminConfig}
  <Card>
    <CardHeader>
      <CardTitle>Metadata Enrichment</CardTitle>
      <CardDescription>External providers for fetching book metadata and covers</CardDescription>
    </CardHeader>
    <CardContent class="space-y-1">
      {#each [
        { label: 'Hardcover', key: 'HARDCOVER_API_KEY', dbKey: 'hardcover_api_key', configured: adminConfig.hardcover_configured, note: 'High-quality curated data, mood tags', url: 'https://hardcover.app/account/api', isTextArea: false },
        { label: 'Amazon', key: 'AMAZON_COOKIE', dbKey: 'amazon_cookie', configured: adminConfig.amazon_configured, note: 'Book data & covers — paste browser Cookie header', url: null, isTextArea: true },
        { label: 'Comicvine', key: 'COMICVINE_API_KEY', dbKey: 'comicvine_api_key', configured: adminConfig.comicvine_configured, note: 'Comics & graphic novels', url: 'https://comicvine.gamespot.com/api/', isTextArea: false },
        { label: 'Google Books', key: 'GOOGLE_BOOKS_API_KEY', dbKey: 'google_books_api_key', configured: adminConfig.google_books_configured, note: 'Broad coverage (optional key)', url: null, isTextArea: false },
        { label: 'ISBNDB', key: 'ISBNDB_API_KEY', dbKey: 'isbndb_api_key', configured: adminConfig.isbndb_configured, note: 'ISBN database', url: 'https://isbndb.com/apidocs/v2', isTextArea: false },
        { label: 'LibraryThing', key: 'LIBRARYTHING_API_KEY', dbKey: 'librarything_api_key', configured: adminConfig.librarything_configured, note: 'Characters, places, awards (Common Knowledge)', url: 'https://www.librarything.com/developer', isTextArea: false },
      ] as p}
        <div class="rounded-md px-3 py-2.5 text-sm {p.configured ? 'bg-green-50/50 dark:bg-green-950/20' : ''}">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              {#if p.configured}
                <CheckCircle class="h-3.5 w-3.5 text-green-500 shrink-0" />
              {:else}
                <AlertCircle class="h-3.5 w-3.5 text-muted-foreground/40 shrink-0" />
              {/if}
              <div>
                <span class="font-medium">{p.label}</span>
                <span class="ml-2 text-xs text-muted-foreground">{p.note}</span>
              </div>
            </div>
            <div class="flex items-center gap-2 shrink-0">
              {#if p.configured}
                <span class="text-xs text-green-600 font-medium">Configured</span>
              {:else if p.url}
                <a href={p.url} target="_blank" rel="noopener" class="text-xs text-primary underline-offset-2 hover:underline">Get key →</a>
              {/if}
              <Button
                size="sm"
                variant="ghost"
                class="h-6 px-2 text-xs"
                onclick={() => toggleEnrichmentEdit(p.dbKey)}
              >
                <Key class="mr-1 h-3 w-3" />{enrichmentExpanded[p.dbKey] ? 'Cancel' : p.configured ? 'Update' : 'Set key'}
              </Button>
            </div>
          </div>

          {#if enrichmentExpanded[p.dbKey]}
            <div class="mt-2 flex gap-2">
              <input
                type={p.isTextArea ? 'text' : 'password'}
                value={enrichmentInput[p.dbKey] ?? ''}
                oninput={(e) => { enrichmentInput[p.dbKey] = (e.target as HTMLInputElement).value; }}
                placeholder={p.configured ? '••••••••  (leave blank to clear)' : `Paste your ${p.label} ${p.isTextArea ? 'cookie' : 'API key'} here`}
                class="flex-1 rounded-md border bg-background px-2 py-1.5 font-mono text-xs outline-none focus:ring-1 focus:ring-ring"
              />
              <Button size="sm" disabled={enrichmentSaving} onclick={() => saveEnrichmentKey(p.dbKey)}>
                {enrichmentSaving ? 'Saving…' : 'Save'}
              </Button>
            </div>
            {#if p.isTextArea}
              <p class="mt-1 text-xs text-muted-foreground">
                Open amazon.com → DevTools (F12) → Network tab → click any request → copy the full <code class="font-mono">Cookie</code> request header value.
                Cookies expire periodically — update here when Amazon stops returning results.
              </p>
            {/if}
          {/if}
        </div>
      {/each}

      {#if enrichmentMsg}
        <p class="text-sm {enrichmentMsgOk ? 'text-green-600 dark:text-green-400' : 'text-destructive'}">{enrichmentMsg}</p>
      {/if}

      <p class="pt-1 text-xs text-muted-foreground">
        Keys are saved in the database and take effect immediately. Open Library works without any key. Env vars in <code class="rounded bg-muted px-1">backend/.env</code> are still respected as fallback.
      </p>
    </CardContent>
  </Card>
{/if}

<!-- Bulk Metadata Enrichment -->
{#if user?.is_admin}
  <Card>
    <CardHeader>
      <CardTitle>Bulk Metadata Enrichment</CardTitle>
      <CardDescription>Fetch missing metadata and covers for many books at once</CardDescription>
    </CardHeader>
    <CardContent class="space-y-4">
      <!-- Filters -->
      <div class="space-y-2">
        <p class="text-sm font-medium">Filters</p>
        <div class="grid grid-cols-2 gap-2 text-sm">
          <label class="flex cursor-pointer items-center gap-2">
            <input type="checkbox" bind:checked={bulkMissingCover} class="rounded" />
            Missing cover
          </label>
          <label class="flex cursor-pointer items-center gap-2">
            <input type="checkbox" bind:checked={bulkMissingDescription} class="rounded" />
            Missing description
          </label>
          <label class="flex cursor-pointer items-center gap-2">
            <input type="checkbox" bind:checked={bulkMissingAuthors} class="rounded" />
            Missing authors
          </label>
          <label class="flex cursor-pointer items-center gap-2 text-amber-700 dark:text-amber-400">
            <input type="checkbox" bind:checked={bulkForce} class="rounded" />
            Force overwrite existing
          </label>
        </div>
        <p class="text-xs text-muted-foreground">
          Locked fields on individual books are always respected, even with Force enabled.
        </p>
      </div>

      <div class="grid grid-cols-2 gap-3">
        <!-- Library filter -->
        <div class="space-y-1">
          <label class="text-xs font-medium text-muted-foreground">Library (optional)</label>
          <select
            bind:value={bulkLibraryId}
            class="w-full rounded-md border bg-background px-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-ring"
          >
            <option value={null}>All libraries</option>
            {#each libraries as lib}
              <option value={lib.id}>{lib.name}</option>
            {/each}
          </select>
        </div>

        <!-- Provider filter -->
        <div class="space-y-1">
          <label class="text-xs font-medium text-muted-foreground">Provider (optional)</label>
          <select
            bind:value={bulkProvider}
            class="w-full rounded-md border bg-background px-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="">Auto (best available)</option>
            <option value="hardcover">Hardcover</option>
            <option value="google_books">Google Books</option>
            <option value="open_library">Open Library</option>
            <option value="amazon">Amazon</option>
            <option value="isbndb">ISBNDB</option>
            <option value="librarything">LibraryThing</option>
            <option value="crossref">CrossRef (academic)</option>
          </select>
        </div>
      </div>

      <!-- Progress -->
      {#if bulkJob && (bulkJob.status === 'running' || bulkJob.status === 'queued')}
        <div class="space-y-2 rounded-md border bg-muted/30 p-3">
          <div class="flex items-center justify-between text-sm">
            <span class="font-medium">
              {bulkJob.status === 'queued' ? 'Queued…' : `Enriching… ${bulkJob.done}/${bulkJob.total}`}
            </span>
            <button
              onclick={cancelBulkEnrich}
              class="flex items-center gap-1 text-xs text-muted-foreground hover:text-destructive"
            >
              <X class="h-3 w-3" />Cancel
            </button>
          </div>
          {#if bulkJob.total > 0}
            <div class="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div
                class="h-full rounded-full bg-primary transition-all"
                style="width: {Math.round((bulkJob.done / bulkJob.total) * 100)}%"
              ></div>
            </div>
          {/if}
          {#if bulkJob.current}
            <p class="truncate text-xs text-muted-foreground" title={bulkJob.current}>
              {bulkJob.current}
            </p>
          {/if}
        </div>
      {:else if bulkJob && bulkJob.status === 'done'}
        <div class="flex items-center gap-2 rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm dark:border-green-800 dark:bg-green-950/30">
          <CheckCircle class="h-4 w-4 shrink-0 text-green-500" />
          <span>{bulkJob.done - bulkJob.failed} enriched · {bulkJob.failed} failed · {bulkJob.total} total</span>
        </div>
      {/if}

      {#if bulkMsg}
        <p class="text-sm {bulkMsgOk ? 'text-green-600 dark:text-green-400' : 'text-destructive'}">{bulkMsg}</p>
      {/if}

      <Button
        onclick={startBulkEnrich}
        disabled={bulkStarting || bulkJob?.status === 'running' || bulkJob?.status === 'queued'}
        class="w-full"
      >
        <Sparkles class="mr-2 h-4 w-4" />
        {bulkStarting ? 'Starting…' : 'Run Bulk Enrichment'}
      </Button>
    </CardContent>
  </Card>
{/if}

<!-- Identifier Extraction (ISBN / DOI) -->
{#if user?.is_admin}
  <Card>
    <CardHeader>
      <CardTitle>Identifier Extraction</CardTitle>
      <CardDescription>Scan book file content for ISBNs and DOIs not found in metadata</CardDescription>
    </CardHeader>
    <CardContent class="space-y-4">
      <p class="text-sm text-muted-foreground">
        Scans EPUB content pages and PDF front/back matter for ISBN-10, ISBN-13, and DOI patterns.
        Only processes books missing an ISBN or DOI. Validates checksums before storing.
      </p>

      {#if idJob && (idJob.status === 'running' || idJob.status === 'queued')}
        <div class="space-y-2 rounded-md border bg-muted/30 p-3">
          <div class="flex items-center justify-between text-sm">
            <span class="font-medium">
              {idJob.status === 'queued' ? 'Queued…' : `Scanning… ${idJob.done}/${idJob.total}`}
            </span>
          </div>
          {#if idJob.total > 0}
            <div class="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div
                class="h-full rounded-full bg-primary transition-all"
                style="width: {Math.round((idJob.done / idJob.total) * 100)}%"
              ></div>
            </div>
          {/if}
          <p class="text-xs text-muted-foreground">
            {idJob.found_isbn} ISBNs · {idJob.found_doi} DOIs found so far
          </p>
        </div>
      {:else if idJob && idJob.status === 'done'}
        <div class="flex items-center gap-2 rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm dark:border-green-800 dark:bg-green-950/30">
          <CheckCircle class="h-4 w-4 shrink-0 text-green-500" />
          <span>{idJob.found_isbn} ISBNs · {idJob.found_doi} DOIs found · {idJob.failed} failed</span>
        </div>
      {/if}

      {#if idMsg}
        <p class="text-sm {idMsgOk ? 'text-green-600 dark:text-green-400' : 'text-destructive'}">{idMsg}</p>
      {/if}

      <Button
        onclick={startBulkIdentifiers}
        disabled={idStarting || idJob?.status === 'running' || idJob?.status === 'queued'}
        class="w-full"
      >
        <Key class="mr-2 h-4 w-4" />
        {idStarting ? 'Starting…' : 'Extract ISBNs & DOIs from All Books'}
      </Button>
    </CardContent>
  </Card>
{/if}

<!-- Filename Metadata Extraction -->
{#if user?.is_admin}
  <Card>
    <CardHeader>
      <CardTitle>Filename Metadata Extraction</CardTitle>
      <CardDescription>Parse title and author from filenames for books with missing metadata</CardDescription>
    </CardHeader>
    <CardContent class="space-y-4">
      <p class="text-sm text-muted-foreground">
        Detects patterns like "Title - Author.epub" and "Author/Title.epub".
        Only updates books currently missing a title or author.
      </p>

      {#if fnJob && (fnJob.status === 'running' || fnJob.status === 'queued')}
        <div class="space-y-2 rounded-md border bg-muted/30 p-3">
          <span class="text-sm font-medium">{fnMsg}</span>
          {#if fnJob.total > 0}
            <div class="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div class="h-full rounded-full bg-primary transition-all" style="width: {Math.round((fnJob.done / fnJob.total) * 100)}%"></div>
            </div>
          {/if}
        </div>
      {:else if fnJob && fnJob.status === 'done'}
        <div class="flex items-center gap-2 rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm dark:border-green-800 dark:bg-green-950/30">
          <CheckCircle class="h-4 w-4 shrink-0 text-green-500" />
          <span>{fnMsg}</span>
        </div>
      {/if}

      {#if fnMsg && !fnJob}
        <p class="text-sm text-muted-foreground">{fnMsg}</p>
      {/if}

      <Button onclick={startFilenameExtract} disabled={fnStarting || fnJob?.status === 'running'} class="w-full">
        <FileText class="mr-2 h-4 w-4" />
        {fnStarting ? 'Starting…' : 'Extract Metadata from Filenames'}
      </Button>
    </CardContent>
  </Card>
{/if}
