<script lang="ts">
  import { Feather, Plus, X, Check, Loader2, Pencil, Trash2 } from 'lucide-svelte';
  import * as api from '$lib/api/client';
  import type { Marginalium, MarginaliumKind } from '$lib/types/index';

  interface Props {
    bookId: number;
    currentLocation?: string;
    onClose: () => void;
  }

  let { bookId, currentLocation, onClose }: Props = $props();

  const KIND_COLORS: Record<MarginaliumKind, string> = {
    observation: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
    insight:     'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
    question:    'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
    theme:       'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300',
    symbol:      'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300',
    character:   'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300',
    parallel:    'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-300',
    structure:   'bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300',
    context:     'bg-teal-100 text-teal-700 dark:bg-teal-900/40 dark:text-teal-300',
    esoteric:    'bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300',
    boring:      'bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-300',
  };

  const KINDS: { value: MarginaliumKind; label: string }[] = [
    { value: 'observation', label: 'Obs' },
    { value: 'insight',     label: 'Insight' },
    { value: 'question',    label: 'Q?' },
    { value: 'theme',       label: 'Theme' },
    { value: 'symbol',      label: 'Symbol' },
    { value: 'character',   label: 'Char' },
    { value: 'parallel',    label: 'Parallel' },
    { value: 'structure',   label: 'Structure' },
    { value: 'context',     label: 'Context' },
    { value: 'esoteric',    label: 'Esoteric' },
    { value: 'boring',      label: 'Boring' },
  ];

  let notes = $state<Marginalium[]>([]);
  let loading = $state(false);
  let showForm = $state(false);
  let saving = $state(false);
  let editingId = $state<number | null>(null);
  let formKind = $state<MarginaliumKind>('observation');
  let formContent = $state('');
  let formLocation = $state('');
  let formChapter = $state('');

  function locationMatches(noteLocation: string, current: string): boolean {
    if (!noteLocation || !current) return false;
    if (noteLocation === current) return true;
    // page:N numeric match
    const cp = current.match(/^page:(\d+)$/);
    const np = noteLocation.match(/^page:(\d+)$/);
    if (cp && np) return cp[1] === np[1];
    // EPUB CFI: match on first 60 chars for approximate "same area"
    if (current.startsWith('epubcfi(') && noteLocation.startsWith('epubcfi(')) {
      return noteLocation.slice(0, 60) === current.slice(0, 60);
    }
    return false;
  }

  let currentNotes = $derived(
    currentLocation
      ? notes.filter(n => n.location && locationMatches(n.location, currentLocation))
      : []
  );

  let otherNotes = $derived(
    currentLocation
      ? notes.filter(n => !n.location || !locationMatches(n.location, currentLocation))
      : notes
  );

  async function load() {
    loading = true;
    try { notes = await api.getMarginalia(bookId); } catch {}
    loading = false;
  }

  function openCreate() {
    editingId = null;
    formKind = 'observation';
    formContent = '';
    formLocation = currentLocation ?? '';
    formChapter = '';
    showForm = true;
  }

  function openEdit(m: Marginalium) {
    editingId = m.id;
    formKind = m.kind;
    formContent = m.content;
    formLocation = m.location ?? '';
    formChapter = m.chapter ?? '';
    showForm = true;
  }

  async function save() {
    if (!formContent.trim()) return;
    saving = true;
    try {
      if (editingId !== null) {
        // Preserve fields not exposed in the quick-edit form (tags, reading_level, etc.)
        const existing = notes.find(n => n.id === editingId);
        const updated = await api.updateMarginalium(editingId, {
          kind: formKind,
          content: formContent.trim(),
          location: formLocation.trim() || null,
          chapter: formChapter.trim() || null,
          reading_level: existing?.reading_level ?? null,
          tags: existing?.tags ?? [],
          related_refs: existing?.related_refs ?? [],
          commentator: existing?.commentator ?? null,
          source: existing?.source ?? null,
        });
        notes = notes.map(n => n.id === editingId ? updated : n);
      } else {
        const created = await api.createMarginalium({
          book_id: bookId,
          kind: formKind,
          content: formContent.trim(),
          location: formLocation.trim() || null,
          chapter: formChapter.trim() || null,
        });
        notes = [created, ...notes];
      }
      showForm = false;
      editingId = null;
    } catch {}
    saving = false;
  }

  async function remove(id: number) {
    if (!confirm('Delete this note?')) return;
    try {
      await api.deleteMarginalium(id);
      notes = notes.filter(n => n.id !== id);
    } catch {}
  }

  // Auto-update location in open form when page turns
  $effect(() => {
    if (showForm && editingId === null && currentLocation) {
      formLocation = currentLocation;
    }
  });

  $effect(() => {
    void bookId;
    load();
  });

  function locationLabel(loc: string): string {
    const m = loc.match(/^page:(\d+)$/);
    return m ? `p.${m[1]}` : loc.slice(0, 28);
  }
</script>

<div class="flex h-full flex-col bg-background text-sm">
  <!-- Header -->
  <div class="flex shrink-0 items-center justify-between border-b px-3 py-2">
    <div class="flex items-center gap-1.5">
      <Feather class="h-4 w-4 text-primary" />
      <span class="font-semibold">Notes</span>
      {#if notes.length > 0}
        <span class="text-xs text-muted-foreground">({notes.length})</span>
      {/if}
    </div>
    <div class="flex items-center gap-1">
      <button
        class="flex items-center gap-1 rounded bg-primary px-2 py-1 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
        onclick={openCreate}
      >
        <Plus class="h-3 w-3" /> Add
      </button>
      <button
        class="ml-1 rounded p-1 hover:bg-muted transition-colors"
        onclick={onClose}
        aria-label="Close"
      >
        <X class="h-4 w-4 text-muted-foreground" />
      </button>
    </div>
  </div>

  <!-- Quick-add / edit form -->
  {#if showForm}
    <div class="shrink-0 space-y-2 border-b bg-muted/30 px-3 py-2.5">
      <p class="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {editingId !== null ? 'Edit note' : 'New note'}
      </p>

      <!-- Kind pills -->
      <div class="flex flex-wrap gap-1">
        {#each KINDS as k}
          <button
            class="rounded-full px-2 py-0.5 text-[10px] font-medium transition-colors {formKind === k.value ? KIND_COLORS[k.value] + ' ring-1 ring-current' : 'bg-muted text-muted-foreground hover:bg-accent'}"
            onclick={() => (formKind = k.value)}
          >{k.label}</button>
        {/each}
      </div>

      <textarea
        bind:value={formContent}
        placeholder="Your note…"
        rows={3}
        class="w-full resize-none rounded border bg-background px-2.5 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
      ></textarea>

      <input
        bind:value={formChapter}
        placeholder="Chapter / section (optional)"
        class="w-full rounded border bg-background px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
      />

      {#if formLocation}
        <p class="font-mono text-[10px] text-muted-foreground truncate">@ {locationLabel(formLocation)}</p>
      {/if}

      <div class="flex gap-1.5">
        <button
          class="flex items-center gap-1 rounded bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-50 transition-opacity"
          disabled={saving || !formContent.trim()}
          onclick={save}
        >
          {#if saving}<Loader2 class="h-3 w-3 animate-spin" />{:else}<Check class="h-3 w-3" />{/if}
          Save
        </button>
        <button
          class="rounded border px-3 py-1.5 text-xs font-medium hover:bg-muted transition-colors"
          onclick={() => { showForm = false; editingId = null; }}
        >Cancel</button>
      </div>
    </div>
  {/if}

  <!-- Notes list -->
  <div class="flex-1 overflow-y-auto">
    {#if loading}
      <div class="flex justify-center py-10">
        <Loader2 class="h-4 w-4 animate-spin text-muted-foreground" />
      </div>
    {:else if notes.length === 0}
      <div class="flex flex-col items-center gap-2 px-4 py-12 text-center">
        <Feather class="h-8 w-8 text-muted-foreground/25" />
        <p class="text-xs text-muted-foreground">No notes yet.</p>
        <button class="text-xs text-primary underline underline-offset-2" onclick={openCreate}>
          Add your first note
        </button>
      </div>
    {:else}
      <!-- Notes for the current page/location -->
      {#if currentNotes.length > 0}
        <div class="px-3 py-2">
          <p class="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            This page
          </p>
          <div class="space-y-1.5">
            {#each currentNotes as note (note.id)}
              <div class="group relative rounded-md border-l-2 bg-muted/40 pl-2.5 pr-2 py-2 space-y-1"
                style="border-color: var(--note-accent, currentColor)"
              >
                <div class="flex items-center justify-between gap-1">
                  <span class="rounded-full px-1.5 py-0.5 text-[10px] font-medium {KIND_COLORS[note.kind]}">
                    {KINDS.find(k => k.value === note.kind)?.label ?? note.kind}
                  </span>
                  <div class="flex gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button class="rounded p-0.5 hover:bg-muted" onclick={() => openEdit(note)}>
                      <Pencil class="h-2.5 w-2.5 text-muted-foreground" />
                    </button>
                    <button class="rounded p-0.5 hover:bg-muted text-destructive" onclick={() => remove(note.id)}>
                      <Trash2 class="h-2.5 w-2.5" />
                    </button>
                  </div>
                </div>
                <p class="text-xs leading-relaxed">{note.content}</p>
                {#if note.chapter}
                  <p class="text-[10px] text-muted-foreground">{note.chapter}</p>
                {/if}
              </div>
            {/each}
          </div>
        </div>
        {#if otherNotes.length > 0}
          <div class="mx-3 border-t"></div>
        {/if}
      {/if}

      <!-- All other notes -->
      {#if otherNotes.length > 0}
        <div class="px-3 py-2">
          {#if currentNotes.length > 0}
            <p class="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              All notes
            </p>
          {/if}
          <div class="space-y-1.5">
            {#each otherNotes as note (note.id)}
              <div class="group rounded-md border bg-background px-2.5 py-2 space-y-1">
                <div class="flex items-start justify-between gap-1">
                  <div class="flex items-center gap-1 flex-wrap">
                    <span class="rounded-full px-1.5 py-0.5 text-[10px] font-medium {KIND_COLORS[note.kind]}">
                      {KINDS.find(k => k.value === note.kind)?.label ?? note.kind}
                    </span>
                    {#if note.location}
                      <span class="font-mono text-[10px] text-muted-foreground">
                        {locationLabel(note.location)}
                      </span>
                    {/if}
                  </div>
                  <div class="flex shrink-0 gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button class="rounded p-0.5 hover:bg-muted" onclick={() => openEdit(note)}>
                      <Pencil class="h-2.5 w-2.5 text-muted-foreground" />
                    </button>
                    <button class="rounded p-0.5 hover:bg-muted text-destructive" onclick={() => remove(note.id)}>
                      <Trash2 class="h-2.5 w-2.5" />
                    </button>
                  </div>
                </div>
                <p class="text-xs leading-relaxed line-clamp-3">{note.content}</p>
                {#if note.chapter}
                  <p class="text-[10px] text-muted-foreground">{note.chapter}</p>
                {/if}
              </div>
            {/each}
          </div>
        </div>
      {/if}
    {/if}
  </div>
</div>
