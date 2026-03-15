<script lang="ts">
  import { Button } from "$lib/components/ui/button";
  import { Card, CardContent, CardHeader, CardTitle } from "$lib/components/ui/card";
  import { Badge } from "$lib/components/ui/badge";
  import { Separator } from "$lib/components/ui/separator";
  import {
    BookOpen,
    ChevronDown,
    ChevronUp,
    Feather,
    Loader2,
    Pencil,
    Plus,
    Trash2,
    X,
    Check,
    Key,
  } from "lucide-svelte";
  import * as api from "$lib/api/client";
  import type { Marginalium, MarginaliumKind, ReadingLevel } from "$lib/types/index";

  interface Props {
    bookId: number | string;
    esotericEnabled?: boolean;
  }

  let { bookId, esotericEnabled = false }: Props = $props();

  const ALL_KINDS: { value: MarginaliumKind; label: string; description: string }[] = [
    { value: "observation",  label: "Observation",  description: "General note" },
    { value: "insight",      label: "Insight",      description: "Interpretive insight" },
    { value: "question",     label: "Question",     description: "Open question for future reading" },
    { value: "theme",        label: "Theme",        description: "Thematic note" },
    { value: "symbol",       label: "Symbol",       description: "Symbolic interpretation" },
    { value: "character",    label: "Character",    description: "Character analysis" },
    { value: "parallel",     label: "Parallel",     description: "Reference to a parallel passage" },
    { value: "structure",    label: "Structure",    description: "Structural or formal observation" },
    { value: "context",      label: "Context",      description: "Historical or cultural context" },
    { value: "esoteric",     label: "Esoteric",     description: "Hidden-meaning reading" },
    { value: "boring",       label: "Boring",       description: "Fifth Key — boring passages hide dynamite" },
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

  let items = $state<Marginalium[]>([]);
  let loading = $state(false);
  let saving = $state(false);
  let filterKind = $state<MarginaliumKind | "">("");
  let showForm = $state(false);
  let editingId = $state<number | null>(null);

  // Five Keys analysis
  let showFiveKeys = $state(false);
  let fiveKeys = $state<api.FiveKeysAnalysis | null>(null);
  let loadingFiveKeys = $state(false);

  const READING_LEVELS: { value: ReadingLevel; label: string; description: string }[] = [
    { value: "surface",  label: "Surface",  description: "Literal, first-pass reading" },
    { value: "exoteric", label: "Exoteric", description: "Public teaching, accessible meaning" },
    { value: "esoteric", label: "Esoteric", description: "Hidden teaching, deeper meaning" },
    { value: "meta",     label: "Meta",     description: "Structural or authorial observation" },
  ];

  const LEVEL_COLORS: Record<ReadingLevel, string> = {
    surface:  "bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300",
    exoteric: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
    esoteric: "bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300",
    meta:     "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300",
  };

  // Form fields
  let formKind = $state<MarginaliumKind>("observation");
  let formReadingLevel = $state<ReadingLevel | "">("");
  let formContent = $state("");
  let formChapter = $state("");
  let formLocation = $state("");
  let formTags = $state("");
  let formRelated = $state("");
  let formCommentator = $state("");
  let formSource = $state("");

  const availableKinds = $derived(
    esotericEnabled ? ALL_KINDS : ALL_KINDS.filter((k) => k.value !== "esoteric")
  );

  const filtered = $derived(
    filterKind ? items.filter((m) => m.kind === filterKind) : items
  );

  async function load() {
    loading = true;
    try {
      items = await api.getMarginalia(bookId);
    } catch (e) {
      console.error("Failed to load marginalia:", e);
    } finally {
      loading = false;
    }
  }

  function openCreate() {
    editingId = null;
    formKind = "observation";
    formReadingLevel = "";
    formContent = "";
    formChapter = "";
    formLocation = "";
    formTags = "";
    formRelated = "";
    formCommentator = "";
    formSource = "";
    showForm = true;
  }

  function openEdit(m: Marginalium) {
    editingId = m.id;
    formKind = m.kind;
    formReadingLevel = m.reading_level ?? "";
    formContent = m.content;
    formChapter = m.chapter ?? "";
    formLocation = m.location ?? "";
    formTags = (m.tags ?? []).join(", ");
    formRelated = (m.related_refs ?? []).join(", ");
    formCommentator = m.commentator ?? "";
    formSource = m.source ?? "";
    showForm = true;
  }

  function closeForm() {
    showForm = false;
    editingId = null;
  }

  function parseTags(raw: string): string[] {
    return raw.split(",").map((s) => s.trim()).filter(Boolean);
  }

  async function save() {
    if (!formContent.trim()) return;
    saving = true;
    try {
      const payload = {
        kind: formKind,
        reading_level: (formReadingLevel || null) as ReadingLevel | null,
        content: formContent.trim(),
        chapter: formChapter.trim() || null,
        location: formLocation.trim() || null,
        tags: parseTags(formTags),
        related_refs: parseTags(formRelated),
        commentator: formCommentator.trim() || null,
        source: formSource.trim() || null,
      };
      if (editingId !== null) {
        const updated = await api.updateMarginalium(editingId, payload);
        items = items.map((m) => (m.id === editingId ? updated : m));
      } else {
        const created = await api.createMarginalium({ book_id: bookId, ...payload });
        items = [created, ...items];
      }
      closeForm();
    } catch (e) {
      console.error("Failed to save marginalium:", e);
    } finally {
      saving = false;
    }
  }

  async function remove(id: number) {
    if (!confirm("Delete this marginalium?")) return;
    try {
      await api.deleteMarginalium(id);
      items = items.filter((m) => m.id !== id);
    } catch (e) {
      console.error("Failed to delete:", e);
    }
  }

  async function toggleFiveKeys() {
    showFiveKeys = !showFiveKeys;
    if (showFiveKeys && !fiveKeys && !loadingFiveKeys) {
      loadingFiveKeys = true;
      try {
        fiveKeys = await api.getFiveKeys(bookId);
      } catch (e) {
        console.error("Failed to load Five Keys analysis:", e);
      } finally {
        loadingFiveKeys = false;
      }
    }
  }

  $effect(() => {
    void bookId;
    load();
  });
</script>

<Card>
  <CardHeader class="flex flex-row items-center justify-between">
    <div class="flex items-center gap-2">
      <Feather class="h-5 w-5 text-primary" />
      <CardTitle class="text-lg">Marginalia</CardTitle>
      {#if items.length > 0}
        <Badge variant="secondary">{items.length}</Badge>
      {/if}
    </div>
    <div class="flex items-center gap-1.5">
      {#if items.length > 0}
        <Button variant="ghost" size="sm" class="h-7 gap-1 text-xs text-muted-foreground" onclick={toggleFiveKeys} title="Straussian Five Keys analysis">
          <Key class="h-3.5 w-3.5" />
          Five Keys
          {#if showFiveKeys}<ChevronUp class="h-3 w-3" />{:else}<ChevronDown class="h-3 w-3" />{/if}
        </Button>
      {/if}
      <Button size="sm" onclick={openCreate}>
        <Plus class="mr-1.5 h-4 w-4" /> Add
      </Button>
    </div>
  </CardHeader>

  <CardContent class="space-y-3">
    <!-- Five Keys Analysis panel -->
    {#if showFiveKeys}
      <div class="rounded-md border bg-muted/20 p-3 space-y-3 text-xs">
        <div class="flex items-center gap-1.5 font-medium text-muted-foreground uppercase tracking-wide text-[10px]">
          <Key class="h-3 w-3" /> Straussian Five Keys
        </div>

        {#if loadingFiveKeys}
          <div class="flex justify-center py-3"><Loader2 class="h-4 w-4 animate-spin text-muted-foreground" /></div>
        {:else if fiveKeys}
          <!-- Key 1: Center -->
          <div>
            <p class="font-semibold text-foreground mb-1">① Center passage <span class="font-normal text-muted-foreground">(note {Math.ceil(fiveKeys.total / 2)} of {fiveKeys.total})</span></p>
            {#if fiveKeys.center}
              <div class="rounded border-l-2 border-amber-400 bg-background pl-2 py-1 space-y-0.5">
                <p class="leading-snug text-foreground">{fiveKeys.center.content}</p>
                {#if fiveKeys.center.chapter}
                  <p class="text-muted-foreground">{fiveKeys.center.chapter}{fiveKeys.center.location ? ` · ${fiveKeys.center.location}` : ""}</p>
                {/if}
              </div>
            {:else}
              <p class="text-muted-foreground italic">No notes yet.</p>
            {/if}
          </div>

          <!-- Key 2: Contradictions -->
          <div>
            <p class="font-semibold text-foreground mb-1">② Contradictions <span class="font-normal text-muted-foreground">({fiveKeys.contradictions.length} esoteric)</span></p>
            {#if fiveKeys.contradictions.length === 0}
              <p class="text-muted-foreground italic">No esoteric notes yet.</p>
            {:else}
              <div class="space-y-1">
                {#each fiveKeys.contradictions.slice(0, 3) as n}
                  <div class="rounded border-l-2 border-violet-400 bg-background pl-2 py-1">
                    <p class="leading-snug text-foreground line-clamp-2">{n.content}</p>
                    {#if n.chapter}<p class="text-muted-foreground">{n.chapter}</p>{/if}
                  </div>
                {/each}
                {#if fiveKeys.contradictions.length > 3}
                  <p class="text-muted-foreground">+{fiveKeys.contradictions.length - 3} more</p>
                {/if}
              </div>
            {/if}
          </div>

          <!-- Key 3: Silence -->
          <div>
            <p class="font-semibold text-foreground mb-1">③ Silence <span class="font-normal text-muted-foreground">(possible gaps)</span></p>
            {#if fiveKeys.silent_chapters.length === 0}
              <p class="text-muted-foreground italic">No detected gaps in chapter sequence.</p>
            {:else}
              <div class="flex flex-wrap gap-1">
                {#each fiveKeys.silent_chapters as ch}
                  <span class="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">{ch}</span>
                {/each}
              </div>
            {/if}
          </div>

          <!-- Key 4: Repetitions -->
          <div>
            <p class="font-semibold text-foreground mb-1">④ Repetitions <span class="font-normal text-muted-foreground">({fiveKeys.repetitions.length} parallels)</span></p>
            {#if fiveKeys.repetitions.length === 0}
              <p class="text-muted-foreground italic">No parallel or cross-referenced notes yet.</p>
            {:else}
              <div class="space-y-1">
                {#each fiveKeys.repetitions.slice(0, 3) as n}
                  <div class="rounded border-l-2 border-cyan-400 bg-background pl-2 py-1">
                    <p class="leading-snug text-foreground line-clamp-2">{n.content}</p>
                    {#if n.related_refs && n.related_refs.length > 0}
                      <p class="text-muted-foreground">→ {n.related_refs.join(", ")}</p>
                    {/if}
                  </div>
                {/each}
                {#if fiveKeys.repetitions.length > 3}
                  <p class="text-muted-foreground">+{fiveKeys.repetitions.length - 3} more</p>
                {/if}
              </div>
            {/if}
          </div>

          <!-- Key 5: Boring passages -->
          <div>
            <p class="font-semibold text-foreground mb-1">⑤ Boring passages <span class="font-normal text-muted-foreground">({fiveKeys.boring.length})</span></p>
            {#if fiveKeys.boring.length === 0}
              <p class="text-muted-foreground italic">Mark a note "Boring" to flag passages hiding dynamite.</p>
            {:else}
              <div class="space-y-1">
                {#each fiveKeys.boring as n}
                  <div class="rounded border-l-2 border-stone-400 bg-background pl-2 py-1">
                    <p class="leading-snug text-foreground line-clamp-2">{n.content}</p>
                    {#if n.chapter}<p class="text-muted-foreground">{n.chapter}</p>{/if}
                  </div>
                {/each}
              </div>
            {/if}
          </div>
        {/if}
      </div>
    {/if}

    <!-- Add / edit form -->
    {#if showForm}
      <div class="space-y-3 rounded-md border bg-muted/30 p-3">
        <p class="text-xs font-medium text-muted-foreground">
          {editingId !== null ? "Edit marginalium" : "New marginalium"}
        </p>

        <!-- Kind selector -->
        <div class="flex flex-wrap gap-1.5">
          {#each availableKinds as k}
            <button
              class="rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors {formKind === k.value ? KIND_COLORS[k.value] + ' ring-1 ring-current' : 'bg-muted text-muted-foreground hover:bg-accent'}"
              onclick={() => (formKind = k.value)}
              title={k.description}
            >{k.label}</button>
          {/each}
        </div>

        <!-- Reading depth level -->
        <div>
          <p class="mb-1 text-xs text-muted-foreground">Reading depth</p>
          <div class="flex flex-wrap gap-1.5">
            <button
              class="rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors {formReadingLevel === '' ? 'bg-muted-foreground/20 text-muted-foreground ring-1 ring-muted-foreground/30' : 'bg-muted text-muted-foreground hover:bg-accent'}"
              onclick={() => (formReadingLevel = "")}
            >None</button>
            {#each READING_LEVELS as lvl}
              <button
                class="rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors {formReadingLevel === lvl.value ? LEVEL_COLORS[lvl.value] + ' ring-1 ring-current' : 'bg-muted text-muted-foreground hover:bg-accent'}"
                onclick={() => (formReadingLevel = lvl.value)}
                title={lvl.description}
              >{lvl.label}</button>
            {/each}
          </div>
        </div>

        <!-- Content -->
        <textarea
          bind:value={formContent}
          placeholder="Your note…"
          rows={4}
          class="w-full rounded-md border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-y"
        ></textarea>

        <!-- Optional fields in a 2-col grid -->
        <div class="grid grid-cols-2 gap-2">
          <div>
            <p class="mb-1 text-xs text-muted-foreground">Chapter / section</p>
            <input
              bind:value={formChapter}
              placeholder="e.g. Book III"
              class="w-full rounded-md border bg-background px-2.5 py-1.5 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
          </div>
          <div>
            <p class="mb-1 text-xs text-muted-foreground">Location (CFI, page, line…)</p>
            <input
              bind:value={formLocation}
              placeholder="e.g. 3.120"
              class="w-full rounded-md border bg-background px-2.5 py-1.5 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
          </div>
          <div>
            <p class="mb-1 text-xs text-muted-foreground">Tags (comma-separated)</p>
            <input
              bind:value={formTags}
              placeholder="e.g. theodicy, fate"
              class="w-full rounded-md border bg-background px-2.5 py-1.5 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
          </div>
          <div>
            <p class="mb-1 text-xs text-muted-foreground">Related refs (comma-separated)</p>
            <input
              bind:value={formRelated}
              placeholder="e.g. 9.502, 22.35"
              class="w-full rounded-md border bg-background px-2.5 py-1.5 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
          </div>
        </div>

        <!-- Attribution row -->
        <div class="grid grid-cols-2 gap-2">
          <div>
            <p class="mb-1 text-xs text-muted-foreground">Commentator (optional)</p>
            <input
              bind:value={formCommentator}
              placeholder="e.g. Leo Strauss"
              class="w-full rounded-md border bg-background px-2.5 py-1.5 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
          </div>
          <div>
            <p class="mb-1 text-xs text-muted-foreground">Source</p>
            <input
              bind:value={formSource}
              placeholder="e.g. Persecution and the Art of Writing, p. 42"
              class="w-full rounded-md border bg-background px-2.5 py-1.5 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
          </div>
        </div>

        <div class="flex gap-2">
          <Button size="sm" class="h-7 text-xs" disabled={saving || !formContent.trim()} onclick={save}>
            {#if saving}<Loader2 class="mr-1 h-3 w-3 animate-spin" />{:else}<Check class="mr-1 h-3 w-3" />{/if}
            Save
          </Button>
          <Button variant="outline" size="sm" class="h-7 text-xs" onclick={closeForm}>
            <X class="mr-1 h-3 w-3" /> Cancel
          </Button>
        </div>
      </div>
    {/if}

    <!-- Kind filter -->
    {#if items.length > 0}
      <div class="flex flex-wrap gap-1.5">
        <button
          class="rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors {filterKind === '' ? 'bg-foreground text-background' : 'bg-muted text-muted-foreground hover:bg-accent'}"
          onclick={() => (filterKind = "")}
        >All</button>
        {#each availableKinds.filter((k) => items.some((m) => m.kind === k.value)) as k}
          <button
            class="rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors {filterKind === k.value ? KIND_COLORS[k.value] + ' ring-1 ring-current' : 'bg-muted text-muted-foreground hover:bg-accent'}"
            onclick={() => (filterKind = filterKind === k.value ? "" : k.value)}
          >{k.label} ({items.filter((m) => m.kind === k.value).length})</button>
        {/each}
      </div>
    {/if}

    <!-- Empty state -->
    {#if !loading && items.length === 0 && !showForm}
      <p class="py-4 text-center text-sm text-muted-foreground">
        No marginalia yet. Click "Add" to write a scholarly note on this book.
      </p>
    {/if}

    {#if loading}
      <div class="flex justify-center py-6">
        <Loader2 class="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    {/if}

    <!-- List -->
    {#each filtered as m (m.id)}
      <div class="group rounded-md border p-3 space-y-1.5">
        <div class="flex items-start justify-between gap-2">
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
          <div class="flex shrink-0 gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
            <Button variant="ghost" size="sm" class="h-6 w-6 p-0" onclick={() => openEdit(m)}>
              <Pencil class="h-3 w-3" />
            </Button>
            <Button variant="ghost" size="sm" class="h-6 w-6 p-0 text-destructive hover:text-destructive" onclick={() => remove(m.id)}>
              <Trash2 class="h-3 w-3" />
            </Button>
          </div>
        </div>

        <p class="text-sm leading-relaxed">{m.content}</p>

        {#if m.chapter || m.location}
          <p class="text-[11px] text-muted-foreground">
            {[m.chapter, m.location].filter(Boolean).join(" · ")}
          </p>
        {/if}

        {#if m.tags && m.tags.length > 0}
          <div class="flex flex-wrap gap-1">
            {#each m.tags as tag}
              <span class="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">{tag}</span>
            {/each}
          </div>
        {/if}

        {#if m.related_refs && m.related_refs.length > 0}
          <p class="text-[11px] text-muted-foreground">
            → {m.related_refs.join(", ")}
          </p>
        {/if}

        {#if m.commentator}
          <p class="text-[11px] italic text-muted-foreground">
            — {m.commentator}{m.source ? `, ${m.source}` : ""}
          </p>
        {/if}
      </div>
    {/each}
  </CardContent>
</Card>
