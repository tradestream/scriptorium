<script lang="ts">
  import { Button } from "$lib/components/ui/button";
  import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "$lib/components/ui/card";
  import { CheckCircle, AlertCircle, X, FileCode, ImageUp } from "lucide-svelte";
  import * as api from "$lib/api/client";
  import type { LayoutData } from '../$types';

  let { data }: { data: LayoutData } = $props();
  let user = $derived(data.user);

  // Bulk Markdown Generation
  let mdJob = $state<{ job_id: string; status: string; total: number; done: number; failed: number; skipped: number; current: string } | null>(null);
  let mdStarting = $state(false);
  let mdMsg = $state('');
  let mdMsgOk = $state(true);
  let _mdPollTimer: ReturnType<typeof setInterval> | null = null;

  function _stopMdPoll() {
    if (_mdPollTimer) { clearInterval(_mdPollTimer); _mdPollTimer = null; }
  }

  async function _pollMdJob(jobId: string) {
    try {
      mdJob = await api.getBulkMarkdownJob(jobId);
      if (mdJob.status === 'done' || mdJob.status === 'cancelled') {
        _stopMdPoll();
        const converted = mdJob.done - mdJob.failed - mdJob.skipped;
        mdMsg = `Done — ${converted} converted, ${mdJob.skipped} skipped, ${mdJob.failed} failed`;
        mdMsgOk = true;
      }
    } catch { _stopMdPoll(); }
  }

  async function startBulkMarkdown() {
    mdStarting = true;
    mdMsg = '';
    mdJob = null;
    _stopMdPoll();
    try {
      const r = await api.startBulkMarkdown();
      mdMsg = `Job started — ${r.total} books to process`;
      mdMsgOk = true;
      mdJob = { job_id: r.job_id, status: 'queued', total: r.total, done: 0, failed: 0, skipped: 0, current: '' };
      _mdPollTimer = setInterval(() => _pollMdJob(r.job_id), 2000);
    } catch (e) {
      mdMsg = e instanceof Error ? e.message : 'Failed to start';
      mdMsgOk = false;
    } finally {
      mdStarting = false;
    }
  }

  // Bulk KEPUB Conversion
  let kepubJob = $state<import('$lib/api/client').BulkKepubJob | null>(null);
  let kepubStarting = $state(false);
  let kepubMsg = $state('');
  let kepubMsgOk = $state(true);
  let kepubHealth = $state<{ available: boolean; path: string | null; version: string | null; fallback_in_use: boolean } | null>(null);
  let _kepubPollTimer: ReturnType<typeof setInterval> | null = null;

  function _stopKepubPoll() {
    if (_kepubPollTimer) { clearInterval(_kepubPollTimer); _kepubPollTimer = null; }
  }

  async function _pollKepubJob(jobId: string) {
    try {
      kepubJob = await api.getBulkKepubJob(jobId);
      if (kepubJob.status === 'done' || kepubJob.status === 'cancelled') {
        _stopKepubPoll();
        const converted = kepubJob.done - kepubJob.failed;
        kepubMsg = `Done — ${converted} converted, ${kepubJob.failed} failed`;
        kepubMsgOk = true;
      }
    } catch { _stopKepubPoll(); }
  }

  async function startBulkKepub() {
    kepubStarting = true;
    kepubMsg = '';
    kepubJob = null;
    _stopKepubPoll();
    try {
      const r = await api.startBulkKepub();
      kepubMsg = r.already_running
        ? `Resumed running job — ${r.total} books`
        : `Job started — ${r.total} EPUBs to convert`;
      kepubMsgOk = true;
      kepubJob = { job_id: r.job_id, status: 'queued', total: r.total, done: 0, failed: 0, current: '', started_at: '' };
      _kepubPollTimer = setInterval(() => _pollKepubJob(r.job_id), 2000);
    } catch (e) {
      kepubMsg = e instanceof Error ? e.message : 'Failed to start';
      kepubMsgOk = false;
    } finally {
      kepubStarting = false;
    }
  }

  async function cancelBulkKepub() {
    if (!kepubJob) return;
    try {
      await api.cancelBulkKepubJob(kepubJob.job_id);
      kepubJob = { ...kepubJob, status: 'cancelled' };
    } catch (e) {
      kepubMsg = e instanceof Error ? e.message : 'Cancel failed';
      kepubMsgOk = false;
    }
  }

  // Cover Upgrade
  let coverUpJob = $state<any>(null);
  let coverUpStarting = $state(false);
  let coverUpMsg = $state('');
  let _coverUpPoll: ReturnType<typeof setInterval> | null = null;

  async function startCoverUpgrade() {
    coverUpStarting = true;
    coverUpMsg = '';
    coverUpJob = null;
    try {
      const r = await api.startCoverUpgrade();
      coverUpMsg = `Scanning ${r.total} low-quality covers…`;
      coverUpJob = { ...r, status: 'queued', done: 0, upgraded: 0, no_match: 0, failed: 0, current: '' };
      _coverUpPoll = setInterval(async () => {
        try {
          coverUpJob = await api.getCoverUpgradeJob(r.job_id);
          coverUpMsg = `Upgrading… ${coverUpJob.done}/${coverUpJob.total} (${coverUpJob.upgraded} upgraded)`;
          if (coverUpJob.status === 'done' || coverUpJob.status === 'cancelled') {
            clearInterval(_coverUpPoll!);
            coverUpMsg = `Done — ${coverUpJob.upgraded} upgraded, ${coverUpJob.no_match} no match, ${coverUpJob.failed} failed`;
            coverUpStarting = false;
          }
        } catch { clearInterval(_coverUpPoll!); coverUpStarting = false; }
      }, 5000);
    } catch (e) {
      coverUpMsg = e instanceof Error ? e.message : 'Failed';
      coverUpStarting = false;
    }
  }

  // Cover Fetch (missing covers)
  let coverFetchJob = $state<any>(null);
  let coverFetchStarting = $state(false);
  let coverFetchMsg = $state('');
  let _coverFetchPoll: ReturnType<typeof setInterval> | null = null;

  async function startCoverFetch() {
    coverFetchStarting = true;
    coverFetchMsg = '';
    coverFetchJob = null;
    try {
      const r = await api.startCoverFetch();
      coverFetchMsg = `Fetching covers for ${r.total} books…`;
      coverFetchJob = { ...r, status: 'queued', done: 0, found: 0, not_found: 0, failed: 0, current: '' };
      _coverFetchPoll = setInterval(async () => {
        try {
          coverFetchJob = await api.getCoverFetchJob(r.job_id);
          coverFetchMsg = `Fetching… ${coverFetchJob.done}/${coverFetchJob.total} (${coverFetchJob.found} found)`;
          if (coverFetchJob.status === 'done' || coverFetchJob.status === 'cancelled') {
            clearInterval(_coverFetchPoll!);
            coverFetchMsg = `Done — ${coverFetchJob.found} covers found, ${coverFetchJob.not_found} not found, ${coverFetchJob.failed} failed`;
            coverFetchStarting = false;
          }
        } catch { clearInterval(_coverFetchPoll!); coverFetchStarting = false; }
      }, 5000);
    } catch (e) {
      coverFetchMsg = e instanceof Error ? e.message : 'Failed';
      coverFetchStarting = false;
    }
  }

  // Reconnect to active background jobs on page load
  $effect(() => {
    if (!data.user?.is_admin) return;
    api.getActiveBulkMarkdownJob().then((job) => {
      if (job && (job.status === 'running' || job.status === 'queued')) {
        mdJob = job;
        mdMsg = `Reconnected — ${job.done}/${job.total} processed`;
        mdMsgOk = true;
        _mdPollTimer = setInterval(() => _pollMdJob(job.job_id), 2000);
      }
    }).catch(() => {});
    api.getActiveBulkKepubJob().then((job) => {
      if (job && (job.status === 'running' || job.status === 'queued')) {
        kepubJob = job;
        kepubMsg = `Reconnected — ${job.done}/${job.total} converted`;
        kepubMsgOk = true;
        _kepubPollTimer = setInterval(() => _pollKepubJob(job.job_id), 2000);
      }
    }).catch(() => {});
    api.getKepubifyHealth().then((h) => { kepubHealth = h; }).catch(() => {});
  });
</script>

<!-- Bulk Markdown Generation -->
{#if user?.is_admin}
  <Card>
    <CardHeader>
      <CardTitle>Markdown Conversion</CardTitle>
      <CardDescription>Pre-convert all book files to LLM-optimized markdown for faster analysis</CardDescription>
    </CardHeader>
    <CardContent class="space-y-4">
      <p class="text-sm text-muted-foreground">
        Generates cached markdown for every book with a text-extractable file (EPUB, PDF, TXT).
        Audiobooks and comics are automatically skipped.
      </p>

      {#if mdJob && (mdJob.status === 'running' || mdJob.status === 'queued')}
        <div class="space-y-2 rounded-md border bg-muted/30 p-3">
          <div class="flex items-center justify-between text-sm">
            <span class="font-medium">
              {mdJob.status === 'queued' ? 'Queued…' : `Converting… ${mdJob.done}/${mdJob.total}`}
            </span>
          </div>
          {#if mdJob.total > 0}
            <div class="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div
                class="h-full rounded-full bg-primary transition-all"
                style="width: {Math.round((mdJob.done / mdJob.total) * 100)}%"
              ></div>
            </div>
          {/if}
          {#if mdJob.current}
            <p class="truncate text-xs text-muted-foreground" title={mdJob.current}>
              {mdJob.current}
            </p>
          {/if}
        </div>
      {:else if mdJob && mdJob.status === 'done'}
        <div class="flex items-center gap-2 rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm dark:border-green-800 dark:bg-green-950/30">
          <CheckCircle class="h-4 w-4 shrink-0 text-green-500" />
          <span>{mdJob.done - mdJob.failed - mdJob.skipped} converted · {mdJob.skipped} skipped · {mdJob.failed} failed</span>
        </div>
      {/if}

      {#if mdMsg}
        <p class="text-sm {mdMsgOk ? 'text-green-600 dark:text-green-400' : 'text-destructive'}">{mdMsg}</p>
      {/if}

      <Button
        onclick={startBulkMarkdown}
        disabled={mdStarting || mdJob?.status === 'running' || mdJob?.status === 'queued'}
        class="w-full"
      >
        <FileCode class="mr-2 h-4 w-4" />
        {mdStarting ? 'Starting…' : 'Generate Markdown for All Books'}
      </Button>
    </CardContent>
  </Card>
{/if}

<!-- Bulk KEPUB Conversion (Kobo) -->
{#if user?.is_admin}
  <Card>
    <CardHeader>
      <CardTitle>KEPUB Conversion (Kobo)</CardTitle>
      <CardDescription>Pre-convert every EPUB so Kobo sync never has to convert on demand</CardDescription>
    </CardHeader>
    <CardContent class="space-y-4">
      <p class="text-sm text-muted-foreground">
        Generates a cached <code class="rounded bg-muted px-1 py-0.5 text-xs">.kepub.epub</code> alongside every EPUB.
        Fixed-layout titles are skipped (Kobo Nickel renders those natively).
        New imports auto-convert on the way in; this button backfills the existing library.
      </p>

      {#if kepubHealth && !kepubHealth.available}
        <div class="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm dark:border-amber-800 dark:bg-amber-950/30">
          <AlertCircle class="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
          <div>
            <p class="font-medium">kepubify not found</p>
            <p class="text-xs text-muted-foreground">
              Conversion will fall back to a renamed copy — Kobo will still accept the file but reading-position spans
              won't be added. Set <code class="rounded bg-muted px-1 py-0.5">KEPUBIFY_PATH</code> to the binary location.
            </p>
          </div>
        </div>
      {:else if kepubHealth?.version}
        <p class="text-xs text-muted-foreground">kepubify {kepubHealth.version}</p>
      {/if}

      {#if kepubJob && (kepubJob.status === 'running' || kepubJob.status === 'queued')}
        <div class="space-y-2 rounded-md border bg-muted/30 p-3">
          <div class="flex items-center justify-between text-sm">
            <span class="font-medium">
              {kepubJob.status === 'queued' ? 'Queued…' : `Converting… ${kepubJob.done}/${kepubJob.total}`}
            </span>
            <Button variant="ghost" size="sm" onclick={cancelBulkKepub}>
              <X class="mr-1 h-3 w-3" /> Cancel
            </Button>
          </div>
          {#if kepubJob.total > 0}
            <div class="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div
                class="h-full rounded-full bg-primary transition-all"
                style="width: {Math.round((kepubJob.done / kepubJob.total) * 100)}%"
              ></div>
            </div>
          {/if}
          {#if kepubJob.failed > 0}
            <p class="text-xs text-amber-600 dark:text-amber-400">{kepubJob.failed} failed (will retry on next sync)</p>
          {/if}
        </div>
      {:else if kepubJob && kepubJob.status === 'done'}
        <div class="flex items-center gap-2 rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm dark:border-green-800 dark:bg-green-950/30">
          <CheckCircle class="h-4 w-4 shrink-0 text-green-500" />
          <span>{kepubJob.done - kepubJob.failed} converted · {kepubJob.failed} failed</span>
        </div>
      {/if}

      {#if kepubMsg}
        <p class="text-sm {kepubMsgOk ? 'text-green-600 dark:text-green-400' : 'text-destructive'}">{kepubMsg}</p>
      {/if}

      <Button
        onclick={startBulkKepub}
        disabled={kepubStarting || kepubJob?.status === 'running' || kepubJob?.status === 'queued'}
        class="w-full"
      >
        <FileCode class="mr-2 h-4 w-4" />
        {kepubStarting ? 'Starting…' : 'Convert All EPUBs to KEPUB'}
      </Button>
    </CardContent>
  </Card>
{/if}

<!-- Cover Quality Upgrade -->
{#if user?.is_admin}
  <Card>
    <CardHeader>
      <CardTitle>Cover Quality Upgrade</CardTitle>
      <CardDescription>Find low-resolution covers and replace them with high-res versions from Apple Books</CardDescription>
    </CardHeader>
    <CardContent class="space-y-4">
      <p class="text-sm text-muted-foreground">
        Scans all covers for quality issues (under 400x600 or 20KB), then searches iTunes for high-resolution replacements using ISBN and title matching.
      </p>

      {#if coverUpJob && (coverUpJob.status === 'running' || coverUpJob.status === 'queued')}
        <div class="space-y-2 rounded-md border bg-muted/30 p-3">
          <span class="text-sm font-medium">{coverUpMsg}</span>
          {#if coverUpJob.total > 0}
            <div class="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div class="h-full rounded-full bg-primary transition-all" style="width: {Math.round((coverUpJob.done / coverUpJob.total) * 100)}%"></div>
            </div>
          {/if}
          {#if coverUpJob.current}
            <p class="truncate text-xs text-muted-foreground">{coverUpJob.current}</p>
          {/if}
        </div>
      {:else if coverUpJob && coverUpJob.status === 'done'}
        <div class="flex items-center gap-2 rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm dark:border-green-800 dark:bg-green-950/30">
          <CheckCircle class="h-4 w-4 shrink-0 text-green-500" />
          <span>{coverUpMsg}</span>
        </div>
      {/if}

      {#if coverUpMsg && !coverUpJob}
        <p class="text-sm text-muted-foreground">{coverUpMsg}</p>
      {/if}

      <Button onclick={startCoverUpgrade} disabled={coverUpStarting || coverUpJob?.status === 'running'} class="w-full">
        <ImageUp class="mr-2 h-4 w-4" />
        {coverUpStarting ? 'Starting…' : 'Upgrade Low-Quality Covers'}
      </Button>
    </CardContent>
  </Card>
{/if}

<!-- Fetch Missing Covers -->
{#if user?.is_admin}
  <Card>
    <CardHeader>
      <CardTitle>Fetch Missing Covers</CardTitle>
      <CardDescription>Find books with no cover image and download covers from Google Books, Open Library, Hardcover, and Amazon</CardDescription>
    </CardHeader>
    <CardContent class="space-y-4">
      <p class="text-sm text-muted-foreground">
        Searches all books that have an ISBN but no cover. Tries multiple metadata providers to find and download cover images.
      </p>

      {#if coverFetchJob && (coverFetchJob.status === 'running' || coverFetchJob.status === 'queued')}
        <div class="space-y-2 rounded-md border bg-muted/30 p-3">
          <span class="text-sm font-medium">{coverFetchMsg}</span>
          {#if coverFetchJob.total > 0}
            <div class="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div class="h-full rounded-full bg-primary transition-all" style="width: {Math.round((coverFetchJob.done / coverFetchJob.total) * 100)}%"></div>
            </div>
          {/if}
          {#if coverFetchJob.current}
            <p class="truncate text-xs text-muted-foreground">{coverFetchJob.current}</p>
          {/if}
        </div>
      {:else if coverFetchJob && coverFetchJob.status === 'done'}
        <div class="flex items-center gap-2 rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm dark:border-green-800 dark:bg-green-950/30">
          <CheckCircle class="h-4 w-4 shrink-0 text-green-500" />
          <span>{coverFetchMsg}</span>
        </div>
      {/if}

      {#if coverFetchMsg && !coverFetchJob}
        <p class="text-sm text-muted-foreground">{coverFetchMsg}</p>
      {/if}

      <Button onclick={startCoverFetch} disabled={coverFetchStarting || coverFetchJob?.status === 'running'} class="w-full">
        <ImageUp class="mr-2 h-4 w-4" />
        {coverFetchStarting ? 'Starting…' : 'Fetch Missing Covers'}
      </Button>
    </CardContent>
  </Card>
{/if}
