<script lang="ts">
  import { Badge } from "$lib/components/ui/badge";
  import { Input } from "$lib/components/ui/input";
  import { Feather, Loader2, Search, BarChart2, ChevronDown, ChevronUp } from "lucide-svelte";
  import * as api from "$lib/api/client";
  import type { MarginaliumWithBook, MarginaliumKind, ReadingLevel } from "$lib/types/index";

  const ALL_KINDS: { value: MarginaliumKind; label: string }[] = [
    { value: "observation",  label: "Observation" },
    { value: "insight",      label: "Insight" },
    { value: "question",     label: "Question" },
    { value: "theme",        label: "Theme" },
    { value: "symbol",       label: "Symbol" },
    { value: "character",    label: "Character" },
    { value: "parallel",     label: "Parallel" },
    { value: "structure",    label: "Structure" },
    { value: "context",      label: "Context" },
    { value: "esoteric",     label: "Esoteric" },
    { value: "boring",       label: "Boring" },
  ];

  const KIND_COLORS: Record<MarginaliumKind, string> = {
    observation: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
    insight:     "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
    question:    "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
    theme:       "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
    symbol:      "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300",
    character:   "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300",
    parallel:    "bg-cyan-100 text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-300",
    structure:   "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300",
    context:     "bg-teal-100 text-teal-700 dark:bg-teal-900/40 dark:text-teal-300",
    esoteric:    "bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300",
    boring:      "bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-300",
  };

  const READING_LEVELS: { value: ReadingLevel; label: string }[] = [
    { value: "surface",  label: "Surface" },
    { value: "exoteric", label: "Exoteric" },
    { value: "esoteric", label: "Esoteric" },
    { value: "meta",     label: "Meta" },
  ];

  const LEVEL_COLORS: Record<ReadingLevel, string> = {
    surface:  "bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300",
    exoteric: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
    esoteric: "bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300",
    meta:     "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300",
  };

  let items = $state<MarginaliumWithBook[]>([]);
  let loading = $state(true);
  let q = $state("");
  let filterKind = $state<MarginaliumKind | "">("");
  let filterLevel = $state<ReadingLevel | "">("");
  let filterCommentator = $state("");

  let showStats = $state(false);
  let stats = $state<api.MarginaliaStats | null>(null);
  let loadingStats = $state(false);

  const filtered = $derived(
    items.filter((m) => {
      if (filterKind && m.kind !== filterKind) return false;
      if (filterLevel && m.reading_level !== filterLevel) return false;
      if (filterCommentator && m.commentator !== filterCommentator) return false;
      if (q) {
        const lower = q.toLowerCase();
        return (
          m.content.toLowerCase().includes(lower) ||
          (m.book_title ?? "").toLowerCase().includes(lower) ||
          (m.chapter ?? "").toLowerCase().includes(lower) ||
          (m.tags ?? []).some((t) => t.toLowerCase().includes(lower)) ||
          (m.commentator ?? "").toLowerCase().includes(lower)
        );
      }
      return true;
    })
  );

  const commentators = $derived(
    [...new Set(items.map((m) => m.commentator).filter((c): c is string => !!c))].sort()
  );

  const activeLevels = $derived(
    READING_LEVELS.filter((l) => items.some((m) => m.reading_level === l.value))
  );

  const kindCounts = $derived(
    ALL_KINDS.map((k) => ({ ...k, count: items.filter((m) => m.kind === k.value).length })).filter(
      (k) => k.count > 0
    )
  );

  async function load() {
    loading = true;
    try {
      items = await api.getMyMarginalia();
    } catch (e) {
      console.error("Failed to load marginalia:", e);
    } finally {
      loading = false;
    }
  }

  async function toggleStats() {
    showStats = !showStats;
    if (showStats && !stats && !loadingStats) {
      loadingStats = true;
      try {
        stats = await api.getMarginaliaStats();
      } catch (e) {
        console.error("Failed to load stats:", e);
      } finally {
        loadingStats = false;
      }
    }
  }

  $effect(() => { load(); });
</script>

<div class="mx-auto max-w-3xl space-y-6 p-6">
  <div class="flex items-center gap-3">
    <Feather class="h-6 w-6 text-primary" />
    <div>
      <h1 class="text-2xl font-semibold">Marginalia</h1>
      <p class="text-sm text-muted-foreground">Scholarly notes across your library</p>
    </div>
    {#if items.length > 0}
      <Badge variant="secondary" class="ml-auto">{items.length}</Badge>
      <button
        class="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
        onclick={toggleStats}
      >
        <BarChart2 class="h-3.5 w-3.5" />
        Stats
        {#if showStats}<ChevronUp class="h-3 w-3" />{:else}<ChevronDown class="h-3 w-3" />{/if}
      </button>
    {/if}
  </div>

  <!-- Stats panel -->
  {#if showStats}
    <div class="rounded-lg border bg-muted/20 p-4 space-y-4 text-sm">
      {#if loadingStats}
        <div class="flex justify-center py-4"><Loader2 class="h-5 w-5 animate-spin text-muted-foreground" /></div>
      {:else if stats}
        <div class="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div class="text-center">
            <p class="text-2xl font-bold">{stats.total}</p>
            <p class="text-xs text-muted-foreground">Total notes</p>
          </div>
          <div class="text-center">
            <p class="text-2xl font-bold">{Object.keys(stats.by_kind).length}</p>
            <p class="text-xs text-muted-foreground">Kinds used</p>
          </div>
          <div class="text-center">
            <p class="text-2xl font-bold">{stats.top_tags.length}</p>
            <p class="text-xs text-muted-foreground">Distinct tags</p>
          </div>
          <div class="text-center">
            <p class="text-2xl font-bold">{stats.top_books.length}</p>
            <p class="text-xs text-muted-foreground">Books annotated</p>
          </div>
        </div>

        {#if stats.top_tags.length > 0}
          <div>
            <p class="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">Top tags</p>
            <div class="flex flex-wrap gap-1.5">
              {#each stats.top_tags.slice(0, 10) as t}
                <span class="rounded bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground">
                  {t.tag} <span class="text-foreground font-medium">{t.count}</span>
                </span>
              {/each}
            </div>
          </div>
        {/if}

        {#if stats.top_books.length > 0}
          <div>
            <p class="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">Most annotated books</p>
            <div class="space-y-1">
              {#each stats.top_books.slice(0, 5) as b}
                <div class="flex items-center gap-2">
                  <div class="h-1.5 rounded-full bg-primary/60" style="width: {Math.round((b.count / stats.top_books[0].count) * 100)}%"></div>
                  <span class="text-xs truncate flex-1">{b.book_title}</span>
                  <span class="text-xs text-muted-foreground shrink-0">{b.count}</span>
                </div>
              {/each}
            </div>
          </div>
        {/if}

        {#if stats.top_commentators.length > 0}
          <div>
            <p class="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">Top commentators</p>
            <div class="flex flex-wrap gap-1.5">
              {#each stats.top_commentators as c}
                <span class="rounded bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground">
                  {c.commentator} <span class="text-foreground font-medium">{c.count}</span>
                </span>
              {/each}
            </div>
          </div>
        {/if}
      {/if}
    </div>
  {/if}

  <!-- Filters -->
  <div class="space-y-3">
    <div class="relative">
      <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
      <Input bind:value={q} placeholder="Search marginalia…" class="pl-9" />
    </div>

    {#if kindCounts.length > 0}
      <div class="flex flex-wrap gap-1.5">
        <button
          class="rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors {filterKind === '' ? 'bg-foreground text-background' : 'bg-muted text-muted-foreground hover:bg-accent'}"
          onclick={() => (filterKind = "")}
        >All ({items.length})</button>
        {#each kindCounts as k}
          <button
            class="rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors {filterKind === k.value ? KIND_COLORS[k.value] + ' ring-1 ring-current' : 'bg-muted text-muted-foreground hover:bg-accent'}"
            onclick={() => (filterKind = filterKind === k.value ? "" : k.value)}
          >{k.label} ({k.count})</button>
        {/each}
      </div>
    {/if}

    {#if activeLevels.length > 0}
      <div class="flex flex-wrap gap-1.5 items-center">
        <span class="text-xs text-muted-foreground self-center">Reading depth:</span>
        <button
          class="rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors {filterLevel === '' ? 'bg-foreground text-background' : 'bg-muted text-muted-foreground hover:bg-accent'}"
          onclick={() => (filterLevel = "")}
        >All</button>
        {#each activeLevels as lvl}
          <button
            class="rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors {filterLevel === lvl.value ? LEVEL_COLORS[lvl.value] + ' ring-1 ring-current' : 'bg-muted text-muted-foreground hover:bg-accent'}"
            onclick={() => (filterLevel = filterLevel === lvl.value ? "" : lvl.value)}
          >{lvl.label}</button>
        {/each}
      </div>
    {/if}

    {#if commentators.length > 0}
      <div class="flex flex-wrap gap-1.5">
        <span class="text-xs text-muted-foreground self-center">Commentator:</span>
        <button
          class="rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors {filterCommentator === '' ? 'bg-foreground text-background' : 'bg-muted text-muted-foreground hover:bg-accent'}"
          onclick={() => (filterCommentator = "")}
        >All</button>
        {#each commentators as c}
          <button
            class="rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors {filterCommentator === c ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground hover:bg-accent'}"
            onclick={() => (filterCommentator = filterCommentator === c ? "" : c)}
          >{c}</button>
        {/each}
      </div>
    {/if}
  </div>

  {#if loading}
    <div class="flex justify-center py-16">
      <Loader2 class="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  {:else if items.length === 0}
    <div class="py-16 text-center text-muted-foreground">
      <Feather class="mx-auto mb-3 h-10 w-10 opacity-20" />
      <p class="text-sm">No marginalia yet. Open a book and add your first scholarly note.</p>
    </div>
  {:else if filtered.length === 0}
    <p class="py-8 text-center text-sm text-muted-foreground">No results match your filter.</p>
  {:else}
    <div class="space-y-3">
      {#each filtered as m (m.id)}
        <a
          href="/book/{m.book_id}"
          class="block rounded-lg border p-4 transition-colors hover:bg-muted/40 space-y-2"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="flex items-center gap-1.5 flex-wrap">
              <span class="rounded-full px-2 py-0.5 text-[11px] font-medium {KIND_COLORS[m.kind]}">
                {ALL_KINDS.find((k) => k.value === m.kind)?.label ?? m.kind}
              </span>
              {#if m.reading_level}
                <span class="rounded-full px-2 py-0.5 text-[11px] font-medium {LEVEL_COLORS[m.reading_level]}">
                  {READING_LEVELS.find((l) => l.value === m.reading_level)?.label ?? m.reading_level}
                </span>
              {/if}
            </div>
            <span class="text-xs text-muted-foreground shrink-0">
              {new Date(m.created_at).toLocaleDateString()}
            </span>
          </div>

          <p class="text-sm leading-relaxed">{m.content}</p>

          <div class="flex items-center gap-2 text-xs text-muted-foreground">
            {#if m.book_title}
              <span class="font-medium text-foreground truncate">{m.book_title}</span>
            {/if}
            {#if m.book_author}
              <span class="shrink-0">· {m.book_author}</span>
            {/if}
            {#if m.chapter}
              <span class="shrink-0">· {m.chapter}</span>
            {/if}
          </div>

          {#if m.tags && m.tags.length > 0}
            <div class="flex flex-wrap gap-1">
              {#each m.tags as tag}
                <span class="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">{tag}</span>
              {/each}
            </div>
          {/if}

          {#if m.commentator}
            <p class="text-[11px] italic text-muted-foreground">
              — {m.commentator}{m.source ? `, ${m.source}` : ""}
            </p>
          {/if}
        </a>
      {/each}
    </div>
  {/if}
</div>
