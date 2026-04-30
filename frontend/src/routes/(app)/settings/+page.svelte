<script lang="ts">
  import { Button } from "$lib/components/ui/button";
  import { Input } from "$lib/components/ui/input";
  import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "$lib/components/ui/card";
  import { Badge } from "$lib/components/ui/badge";
  import { Separator } from "$lib/components/ui/separator";
  import { Plus, RefreshCw, Trash2, Play, CheckCircle, AlertCircle, Copy, Clock, Download, Server, Key, Eye, EyeOff, Users, UserPlus, UserMinus, Lock, Unlock, Headphones, Link2, FileCode, Sparkles, X, ImageUp, FileText, User as UserIcon, BookOpen, Tag as TagIcon, FileBox, Plug, Cog } from "lucide-svelte";
  import { page } from "$app/state";
  import { goto } from "$app/navigation";
  import * as api from "$lib/api/client";
  import type { AdminConfig } from "$lib/api/client";
  import type { Library, LibraryAccess, User as UserType, IngestLog, ApiKey, ApiKeyCreated } from "$lib/types/index";
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();
  let user = $derived(data.user);

  // ── Section nav ────────────────────────────────────────────────────────────
  // 26 settings cards used to live on one scroll-of-doom page. Sectioning
  // them gives users a fighting chance at finding things; URL-sync via
  // ``?section=…`` so deep-links + browser back work.
  type SectionId = 'account' | 'library' | 'metadata' | 'files' | 'integrations' | 'system';
  const SECTIONS: { id: SectionId; label: string; icon: any; adminOnly?: boolean }[] = [
    { id: 'account',      label: 'Account',           icon: UserIcon },
    { id: 'library',      label: 'Library',           icon: BookOpen },
    { id: 'metadata',     label: 'Metadata',          icon: TagIcon, adminOnly: true },
    { id: 'files',        label: 'Files & Conversion', icon: FileBox, adminOnly: true },
    { id: 'integrations', label: 'Integrations',      icon: Plug },
    { id: 'system',       label: 'System',            icon: Cog, adminOnly: true },
  ];

  function _sectionFromUrl(): SectionId {
    const s = page.url.searchParams.get('section') as SectionId | null;
    const match = SECTIONS.find((sec) => sec.id === s);
    // Reject admin-only sections for non-admins so a deep-link doesn't
    // land them on a blank page (every card inside would be gated out).
    if (!match || (match.adminOnly && !data.user?.is_admin)) return 'account';
    return match.id;
  }
  let activeSection = $state<SectionId>(_sectionFromUrl());

  function selectSection(id: SectionId) {
    if (activeSection === id) return;
    activeSection = id;
    const url = new URL(window.location.href);
    url.searchParams.set('section', id);
    goto(url, { replaceState: true, keepFocus: true, noScroll: true });
  }

  // Profile editing
  let profileDisplayName = $state(data.user?.display_name ?? '');
  let savingProfile = $state(false);
  let profileMsg = $state('');

  async function saveProfile() {
    savingProfile = true;
    profileMsg = '';
    try {
      await api.updateProfile({ display_name: profileDisplayName.trim() });
      profileMsg = 'Saved';
      setTimeout(() => profileMsg = '', 2000);
    } catch { /* ignore */ }
    savingProfile = false;
  }

  let libraries = $state<Library[]>([]);
  let showCreateLibrary = $state(false);
  let newLibraryName = $state('');
  let newLibraryPath = $state('');
  let creating = $state(false);
  let createError = $state('');

  let ingestLogs = $state<IngestLog[]>([]);
  let ingestTotal = $state(0);
  let ingestLoading = $state(false);
  let triggering = $state(false);
  let rebuildingIndex = $state(false);
  let rebuildIndexMsg = $state('');

  async function rebuildSearchIndex() {
    rebuildingIndex = true;
    rebuildIndexMsg = '';
    try {
      const result = await api.rebuildSearchIndex();
      rebuildIndexMsg = `Done — ${result.indexed} works indexed.`;
    } catch (e: any) {
      rebuildIndexMsg = e?.message ?? 'Failed to rebuild index.';
    } finally {
      rebuildingIndex = false;
    }
  }
  let ingestMsg = $state('');
  let adminConfig = $state<AdminConfig | null>(null);

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

  async function loadAdminConfig() {
    if (!data.user?.is_admin) return;
    try { adminConfig = await api.getAdminConfig(); } catch { /* non-critical */ }
  }

  $effect(() => { loadAdminConfig(); });

  // ── Naming pattern preview ─────────────────────────────────────────────────
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

  // ── Enrichment keys ────────────────────────────────────────────────────────
  let enrichmentExpanded = $state<Record<string, boolean>>({});
  // Input state: keyed by provider id, value is what the user typed (undefined = not editing)
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
      const result = await api.updateEnrichmentKeys({ [key]: enrichmentInput[key] ?? '' });
      // Refresh adminConfig to reflect new configured state
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

  // ── Devices ────────────────────────────────────────────────────────────────
  let devices = $state<import('$lib/api/client').Device[]>([]);
  async function loadDevices() {
    try { devices = await api.getDevices(); } catch { /* non-critical */ }
  }
  $effect(() => { loadDevices(); });

  async function removeDevice(id: number) {
    await api.deleteDevice(id);
    devices = devices.filter(d => d.id !== id);
  }

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

  // ── Library Access Control ──────────────────────────────────────────────────
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

  async function deleteLibrary(id: number) {
    if (!confirm('Delete this library? Books will be removed from the database but not from disk.')) return;
    await api.deleteLibrary(id);
    await loadLibraries();
  }

  // ── Per-library naming pattern ──────────────────────────────────────────────
  let namingExpanded = $state<Record<number, boolean>>({});
  let libNamingInput = $state<Record<number, string>>({});
  let libNamingSaving = $state<Record<number, boolean>>({});

  function toggleNamingPanel(lib: import('$lib/types/index').Library) {
    namingExpanded[lib.id] = !namingExpanded[lib.id];
  }

  async function saveLibraryNaming(lib: import('$lib/types/index').Library) {
    libNamingSaving[lib.id] = true;
    try {
      const val = libNamingInput[lib.id] ?? '';
      await api.updateLibraryNaming(lib.id, val.trim() || null);
      await loadLibraries();
    } finally {
      libNamingSaving[lib.id] = false;
    }
  }

  // Per-library exclude-patterns panel — mirrors the naming-pattern
  // shape so the settings page stays consistent. Patterns are stored
  // as a JSON array on the model; the UI surfaces them as one pattern
  // per line for easy editing.
  let excludesExpanded = $state<Record<number, boolean>>({});
  let libExcludesInput = $state<Record<number, string>>({});
  let libExcludesSaving = $state<Record<number, boolean>>({});

  function toggleExcludesPanel(lib: import('$lib/types/index').Library) {
    excludesExpanded[lib.id] = !excludesExpanded[lib.id];
  }

  async function saveLibraryExcludes(lib: import('$lib/types/index').Library) {
    libExcludesSaving[lib.id] = true;
    try {
      const raw = libExcludesInput[lib.id] ?? '';
      const patterns = raw
        .split('\n')
        .map((s) => s.trim())
        .filter((s) => s && !s.startsWith('#'));
      // ``null`` clears back to defaults-only; an empty array also
      // clears any custom additions.
      await api.updateLibrary(lib.id, {
        exclude_patterns: patterns.length > 0 ? patterns : null,
      });
      await loadLibraries();
    } finally {
      libExcludesSaving[lib.id] = false;
    }
  }

  // ── API Keys ────────────────────────────────────────────────────────────────
  let apiKeys = $state<ApiKey[]>([]);
  let newKeyName = $state('');
  let creatingKey = $state(false);
  let newlyCreatedKey = $state<ApiKeyCreated | null>(null);
  let showNewKey = $state(false);

  async function loadApiKeys() {
    try { apiKeys = await api.getApiKeys(); } catch { /* non-critical */ }
  }

  $effect(() => { loadApiKeys(); });

  async function createApiKey() {
    if (!newKeyName.trim()) return;
    creatingKey = true;
    try {
      const created = await api.createApiKey(newKeyName.trim());
      newlyCreatedKey = created;
      showNewKey = true;
      newKeyName = '';
      await loadApiKeys();
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Failed to create key');
    } finally { creatingKey = false; }
  }

  async function revokeApiKey(id: number) {
    if (!confirm('Revoke this API key?')) return;
    try { await api.revokeApiKey(id); await loadApiKeys(); }
    catch (e) { alert(e instanceof Error ? e.message : 'Failed'); }
  }

  async function copyKey() {
    if (!newlyCreatedKey) return;
    await navigator.clipboard.writeText(newlyCreatedKey.key);
  }

  // ── Bulk Enrichment ────────────────────────────────────────────────────────
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

  // ── Bulk Identifier Extraction ──────────────────────────────────────────────
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

  // ── Bulk Markdown Generation ────────────────────────────────────────────────
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

  // ── Bulk KEPUB Conversion ──────────────────────────────────────────────────
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

  // ── Cover Upgrade ──────────────────────────────────────────────────────────
  let coverUpJob = $state<any>(null);
  let coverUpStarting = $state(false);
  let coverUpMsg = $state('');
  let _coverUpPoll: ReturnType<typeof setInterval> | null = null;

  // ── Cover Fetch (missing covers) ──────────────────────────────────────────
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

  // ── Filename Metadata Extraction ──────────────────────────────────────────
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

  // ── Kobo compatibility health ──────────────────────────────────────────────
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
    if (data.user?.is_admin && activeSection === 'integrations' && koboHealth === null && !koboHealthLoading) {
      loadKoboHealth();
    }
  });

  // ── Kobo Fonts (USB sideload bundle) ───────────────────────────────────────
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
    if (data.user?.is_admin && activeSection === 'integrations' && koboFonts === null && !koboFontsLoading) {
      loadKoboFonts();
    }
  });

  function formatMB(bytes: number): string {
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  // ── AudiobookShelf ──────────────────────────────────────────────────────────
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

  // ── Reconnect to active background jobs on page load ──────────────────────
  $effect(() => {
    if (!data.user?.is_admin) return;
    // Check for active bulk enrichment job
    api.getActiveBulkEnrichJob().then((job) => {
      if (job && (job.status === 'running' || job.status === 'queued')) {
        bulkJob = job;
        bulkMsg = `Reconnected — ${job.done}/${job.total} processed`;
        bulkMsgOk = true;
        _bulkPollTimer = setInterval(() => _pollBulkJob(job.job_id), 2000);
      }
    }).catch(() => {});
    // Check for active identifier extraction job
    api.getActiveBulkIdentifiersJob().then((job) => {
      if (job && (job.status === 'running' || job.status === 'queued')) {
        idJob = job;
        idMsg = `Reconnected — ${job.done}/${job.total} scanned`;
        idMsgOk = true;
        _idPollTimer = setInterval(() => _pollIdJob(job.job_id), 2000);
      }
    }).catch(() => {});
    // Check for active markdown generation job
    api.getActiveBulkMarkdownJob().then((job) => {
      if (job && (job.status === 'running' || job.status === 'queued')) {
        mdJob = job;
        mdMsg = `Reconnected — ${job.done}/${job.total} processed`;
        mdMsgOk = true;
        _mdPollTimer = setInterval(() => _pollMdJob(job.job_id), 2000);
      }
    }).catch(() => {});
    // Check for active KEPUB conversion job (auto-kicked at startup or manual)
    api.getActiveBulkKepubJob().then((job) => {
      if (job && (job.status === 'running' || job.status === 'queued')) {
        kepubJob = job;
        kepubMsg = `Reconnected — ${job.done}/${job.total} converted`;
        kepubMsgOk = true;
        _kepubPollTimer = setInterval(() => _pollKepubJob(job.job_id), 2000);
      }
    }).catch(() => {});
    // Surface kepubify binary status so users know whether they're
    // getting real KEPUB span wrapping or just renamed copies.
    api.getKepubifyHealth().then((h) => { kepubHealth = h; }).catch(() => {});
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
      // Poll until done
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

<div class="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
  <div>
    <h1 class="text-3xl font-bold tracking-tight">Settings</h1>
    <p class="mt-1 text-muted-foreground">Manage your Scriptorium instance</p>
  </div>

  <div class="mt-6 flex flex-col gap-6 md:flex-row">
    <!-- Sidebar nav -->
    <nav class="md:sticky md:top-8 md:h-fit md:w-56 md:shrink-0">
      <!-- Mobile: horizontal scroll tabs -->
      <div class="-mx-4 flex gap-1 overflow-x-auto px-4 pb-2 md:hidden">
        {#each SECTIONS as s (s.id)}
          {#if !s.adminOnly || user?.is_admin}
            <button
              type="button"
              onclick={() => selectSection(s.id)}
              class="shrink-0 rounded-md px-3 py-1.5 text-sm font-medium {activeSection === s.id ? 'bg-accent text-accent-foreground' : 'text-muted-foreground hover:bg-muted'}"
            >
              {s.label}
            </button>
          {/if}
        {/each}
      </div>
      <!-- Desktop: vertical list -->
      <ul class="hidden space-y-1 md:block">
        {#each SECTIONS as s (s.id)}
          {#if !s.adminOnly || user?.is_admin}
            <li>
              <button
                type="button"
                onclick={() => selectSection(s.id)}
                class="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors {activeSection === s.id ? 'bg-accent text-accent-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground'}"
              >
                <s.icon class="h-4 w-4 shrink-0" />
                {s.label}
              </button>
            </li>
          {/if}
        {/each}
      </ul>
    </nav>

    <!-- Section content -->
    <div class="min-w-0 flex-1 space-y-6">

  <!-- Account -->
  {#if activeSection === 'account'}
  <Card>
    <CardHeader>
      <CardTitle>Account</CardTitle>
      <CardDescription>Your account details</CardDescription>
    </CardHeader>
    <CardContent class="space-y-4">
      <div class="space-y-2">
        <label for="username" class="text-sm font-medium">Username</label>
        <Input id="username" value={user?.username ?? ''} disabled />
      </div>
      <div class="space-y-2">
        <label for="display-name" class="text-sm font-medium">Display Name</label>
        <div class="flex gap-2">
          <Input id="display-name" bind:value={profileDisplayName} placeholder="Your full name" />
          <Button
            variant="outline"
            size="sm"
            onclick={saveProfile}
            disabled={savingProfile}
            class="shrink-0"
          >
            {savingProfile ? 'Saving…' : 'Save'}
          </Button>
        </div>
        {#if profileMsg}
          <p class="text-xs text-green-600 dark:text-green-400">{profileMsg}</p>
        {/if}
      </div>
      <div class="space-y-2">
        <label for="email" class="text-sm font-medium">Email</label>
        <Input id="email" type="email" value={user?.email ?? ''} disabled />
      </div>
      {#if user?.is_admin}
        <Badge variant="outline">Administrator</Badge>
      {/if}
    </CardContent>
  </Card>
  {/if}

  <!-- API Keys -->
  {#if activeSection === 'account'}
  <Card>
    <CardHeader>
      <CardTitle>API Keys</CardTitle>
      <CardDescription>Use API keys to access Scriptorium from scripts or external apps without your password</CardDescription>
    </CardHeader>
    <CardContent class="space-y-4">
      {#if newlyCreatedKey && showNewKey}
        <div class="rounded-md border border-amber-300 bg-amber-50 p-3 dark:border-amber-700 dark:bg-amber-950/30">
          <p class="mb-1.5 text-sm font-medium text-amber-800 dark:text-amber-200">Copy your key now — it won't be shown again</p>
          <div class="flex items-center gap-2">
            <code class="flex-1 truncate rounded bg-background px-2 py-1 font-mono text-xs">{newlyCreatedKey.key}</code>
            <Button size="sm" variant="outline" onclick={copyKey}><Copy class="mr-1.5 h-3.5 w-3.5" />Copy</Button>
            <Button size="sm" variant="ghost" onclick={() => { showNewKey = false; newlyCreatedKey = null; }}>Dismiss</Button>
          </div>
        </div>
      {/if}

      {#if apiKeys.length > 0}
        <div class="space-y-2">
          {#each apiKeys as key}
            <div class="flex items-center justify-between rounded-md border p-3">
              <div>
                <p class="text-sm font-medium">{key.name}</p>
                <p class="font-mono text-xs text-muted-foreground">{key.prefix}…</p>
                <p class="text-xs text-muted-foreground">
                  Created {new Date(key.created_at).toLocaleDateString()}
                  {#if key.last_used_at} · Last used {new Date(key.last_used_at).toLocaleDateString()}{/if}
                </p>
              </div>
              <Button variant="ghost" size="icon" onclick={() => revokeApiKey(key.id)} title="Revoke" class="text-destructive hover:text-destructive">
                <Trash2 class="h-4 w-4" />
              </Button>
            </div>
          {/each}
        </div>
        <Separator />
      {/if}

      <div class="flex gap-2">
        <Input
          placeholder="Key name (e.g. Home Script)"
          bind:value={newKeyName}
          class="flex-1"
          onkeydown={(e) => { if (e.key === 'Enter') createApiKey(); }}
        />
        <Button size="sm" onclick={createApiKey} disabled={creatingKey || !newKeyName.trim()}>
          <Key class="mr-1.5 h-3.5 w-3.5" />{creatingKey ? 'Creating…' : 'Generate'}
        </Button>
      </div>
    </CardContent>
  </Card>
  {/if}

  <!-- Connected Devices -->
  {#if activeSection === 'account'}
  <Card>
    <CardHeader>
      <CardTitle>Connected Devices</CardTitle>
      <CardDescription>E-readers and apps syncing with your account</CardDescription>
    </CardHeader>
    <CardContent class="space-y-2">
      {#if devices.length === 0}
        <p class="text-sm text-muted-foreground">No devices connected yet.</p>
      {:else}
        {#each devices as device}
          <div class="flex items-center justify-between rounded-md border p-3">
            <div>
              <p class="text-sm font-medium">{device.name}</p>
              <p class="text-xs text-muted-foreground capitalize">{device.device_type}{#if device.device_model} · {device.device_model}{/if}</p>
              {#if device.last_synced}
                <p class="text-xs text-muted-foreground">Last synced {new Date(device.last_synced).toLocaleDateString()}</p>
              {/if}
            </div>
            <Button variant="ghost" size="icon" onclick={() => removeDevice(device.id)} title="Remove device" class="text-destructive hover:text-destructive">
              <Trash2 class="h-4 w-4" />
            </Button>
          </div>
        {/each}
      {/if}
    </CardContent>
  </Card>
  {/if}

  <!-- Libraries -->
  {#if activeSection === 'library'}
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
  {/if}

  <!-- Auto-Ingest -->
  {#if user?.is_admin && activeSection === 'library'}
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

  <!-- Metadata Enrichment -->
  {#if user?.is_admin && adminConfig && activeSection === 'metadata'}
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
  {#if user?.is_admin && activeSection === 'metadata'}
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

  <!-- Bulk Markdown Generation -->
  {#if user?.is_admin && activeSection === 'files'}
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
  {#if user?.is_admin && activeSection === 'files'}
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

  <!-- Identifier Extraction (ISBN / DOI) -->
  {#if user?.is_admin && activeSection === 'metadata'}
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

  <!-- Cover Quality Upgrade -->
  {#if user?.is_admin && activeSection === 'files'}
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
  {#if user?.is_admin && activeSection === 'files'}
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

  <!-- Filename Metadata Extraction -->
  {#if user?.is_admin && activeSection === 'metadata'}
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

  <!-- File Naming Pattern -->
  {#if user?.is_admin && adminConfig && activeSection === 'library'}
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

  <!-- AudiobookShelf -->
  {#if user?.is_admin && activeSection === 'integrations'}
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

  <!-- Loose Leaves -->
  {#if user?.is_admin && adminConfig && activeSection === 'library'}
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

  <!-- System Config (admin) -->
  {#if user?.is_admin && adminConfig && activeSection === 'system'}
    <Card>
      <CardHeader>
        <CardTitle>System Configuration</CardTitle>
        <CardDescription>
          Current server settings — edit the <code class="rounded bg-muted px-1 py-0.5 text-xs">.env</code> file to change these
        </CardDescription>
      </CardHeader>
      <CardContent class="space-y-4">
        <!-- Paths -->
        <div class="grid grid-cols-2 gap-3 text-sm">
          <div>
            <p class="font-medium text-muted-foreground">Library Path</p>
            <code class="text-xs">{adminConfig.library_path}</code>
          </div>
          <div>
            <p class="font-medium text-muted-foreground">Ingest Path</p>
            <code class="text-xs">{adminConfig.ingest_path}</code>
          </div>
          <div>
            <p class="font-medium text-muted-foreground">Calibre Path</p>
            <code class="text-xs">{adminConfig.calibre_path}</code>
          </div>
          <div>
            <p class="font-medium text-muted-foreground">LLM Provider</p>
            <span class="flex items-center gap-1 text-xs">
              {adminConfig.llm_provider}
              {#if adminConfig.llm_configured}
                <CheckCircle class="h-3 w-3 text-green-500" />
              {:else}
                <AlertCircle class="h-3 w-3 text-amber-500" />
              {/if}
            </span>
          </div>
        </div>

        <Separator />

        <!-- Ingest preferences -->
        <div>
          <p class="text-sm font-medium">Auto-Ingest Preferences</p>
          <div class="mt-2 grid grid-cols-2 gap-3 text-sm">
            <div>
              <p class="text-xs text-muted-foreground">Auto-Convert</p>
              <p>{adminConfig.ingest_auto_convert ? `Yes → ${adminConfig.ingest_target_format.toUpperCase()}` : 'Disabled'}</p>
            </div>
            <div>
              <p class="text-xs text-muted-foreground">Auto-Enrich</p>
              <p>{adminConfig.ingest_auto_enrich ? `Yes${adminConfig.ingest_default_provider ? ` (${adminConfig.ingest_default_provider})` : ''}` : 'Disabled'}</p>
            </div>
          </div>
          <p class="mt-2 text-xs text-muted-foreground">
            Set <code class="rounded bg-muted px-1">INGEST_AUTO_CONVERT</code>,
            <code class="rounded bg-muted px-1">INGEST_TARGET_FORMAT</code>,
            <code class="rounded bg-muted px-1">INGEST_AUTO_ENRICH</code> in your <code class="rounded bg-muted px-1">.env</code> file.
          </p>
        </div>

        <Separator />

        <!-- OIDC -->
        <div>
          <div class="flex items-center gap-2">
            <p class="text-sm font-medium">Single Sign-On (OIDC)</p>
            {#if adminConfig.oidc_configured}
              <Badge variant="secondary" class="text-xs">Enabled</Badge>
            {:else}
              <Badge variant="outline" class="text-xs text-muted-foreground">Disabled</Badge>
            {/if}
          </div>
          {#if adminConfig.oidc_configured}
            <p class="mt-1 text-xs text-muted-foreground">
              Provider: <code class="rounded bg-muted px-1">{adminConfig.oidc_discovery_url}</code>
            </p>
          {:else}
            <p class="mt-1 text-xs text-muted-foreground">
              Set <code class="rounded bg-muted px-1">OIDC_ENABLED=true</code>,
              <code class="rounded bg-muted px-1">OIDC_DISCOVERY_URL</code>,
              <code class="rounded bg-muted px-1">OIDC_CLIENT_ID</code>, and
              <code class="rounded bg-muted px-1">OIDC_CLIENT_SECRET</code> to enable SSO.
            </p>
          {/if}
        </div>

        <Separator />

        <!-- SMTP -->
        <div>
          <div class="flex items-center gap-2">
            <p class="text-sm font-medium">Email / Send-to-Device (SMTP)</p>
            {#if adminConfig.smtp_configured}
              <Badge variant="secondary" class="text-xs">Configured</Badge>
            {:else}
              <Badge variant="outline" class="text-xs text-muted-foreground">Not configured</Badge>
            {/if}
          </div>
          {#if adminConfig.smtp_configured}
            <div class="mt-2 grid grid-cols-2 gap-3 text-sm">
              <div>
                <p class="text-xs text-muted-foreground">Host</p>
                <p>{adminConfig.smtp_host}:{adminConfig.smtp_port}</p>
              </div>
              <div>
                <p class="text-xs text-muted-foreground">From</p>
                <p>{adminConfig.smtp_from ?? adminConfig.smtp_user}</p>
              </div>
            </div>
          {:else}
            <p class="mt-1 text-xs text-muted-foreground">
              Set <code class="rounded bg-muted px-1">SMTP_HOST</code>, <code class="rounded bg-muted px-1">SMTP_USER</code>,
              <code class="rounded bg-muted px-1">SMTP_PASS</code>, and <code class="rounded bg-muted px-1">SMTP_FROM</code> to enable email delivery.
            </p>
          {/if}
        </div>
      </CardContent>
    </Card>

    <!-- Search Index -->
    <Card>
      <CardHeader>
        <CardTitle>Search Index</CardTitle>
        <CardDescription>Rebuild the full-text search index from scratch</CardDescription>
      </CardHeader>
      <CardContent>
        <p class="text-sm text-muted-foreground">
          Run this if search returns no results or seems stale. Reindexes all works in the database.
        </p>
        <div class="mt-4 flex items-center gap-3">
          <Button variant="outline" onclick={rebuildSearchIndex} disabled={rebuildingIndex}>
            <RefreshCw class="mr-2 h-4 w-4 {rebuildingIndex ? 'animate-spin' : ''}" />
            {rebuildingIndex ? 'Rebuilding…' : 'Rebuild Index'}
          </Button>
          {#if rebuildIndexMsg}
            <span class="text-sm text-muted-foreground">{rebuildIndexMsg}</span>
          {/if}
        </div>
      </CardContent>
    </Card>

    <!-- Backup -->
    <Card>
      <CardHeader>
        <CardTitle>Backup</CardTitle>
        <CardDescription>Download a snapshot of the database and config</CardDescription>
      </CardHeader>
      <CardContent>
        <p class="text-sm text-muted-foreground">
          Creates a <code class="rounded bg-muted px-1 py-0.5 text-xs">.tar.gz</code> archive containing
          the SQLite database and any config files.
        </p>
        <Button class="mt-4" href={api.adminBackupUrl()} download>
          <Download class="mr-2 h-4 w-4" /> Download Backup
        </Button>
      </CardContent>
    </Card>
  {/if}

  <!-- Kobo Compatibility Health -->
  {#if user?.is_admin && activeSection === 'integrations'}
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
  {#if user?.is_admin && activeSection === 'integrations'}
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
  {#if activeSection === 'integrations'}
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
  {/if}

    </div><!-- /section content -->
  </div><!-- /flex -->
</div>
