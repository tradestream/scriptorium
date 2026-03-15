<script lang="ts">
  import { page } from '$app/state';
  import { BookCopy, ChevronLeft, Trash2, Loader2, BookOpen } from 'lucide-svelte';
  import * as api from '$lib/api/client';
  import type { Notebook, NotebookEntry } from '$lib/api/client';

  const KIND_COLORS: Record<string, string> = {
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

  const LEVEL_COLORS: Record<string, string> = {
    surface:  'bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300',
    exoteric: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
    esoteric: 'bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300',
    meta:     'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300',
  };

  const notebookId = $derived(Number(page.params.id));

  let notebook = $state<Notebook | null>(null);
  let entries = $state<NotebookEntry[]>([]);
  let loading = $state(true);
  let notFound = $state(false);

  // Group by book
  const byBook = $derived(
    entries.reduce<Record<number, { title: string; entries: NotebookEntry[] }>>((acc, e) => {
      if (!acc[e.book_id]) acc[e.book_id] = { title: e.book_title ?? `Book ${e.book_id}`, entries: [] };
      acc[e.book_id].entries.push(e);
      return acc;
    }, {})
  );

  async function load() {
    loading = true;
    try {
      const [nbs, ents] = await Promise.all([
        api.getNotebooks(),
        api.getNotebookEntries(notebookId),
      ]);
      notebook = nbs.find(n => n.id === notebookId) ?? null;
      if (!notebook) notFound = true;
      entries = ents;
    } catch {
      notFound = true;
    } finally {
      loading = false;
    }
  }

  async function removeEntry(entryId: number) {
    try {
      await api.removeNotebookEntry(notebookId, entryId);
      entries = entries.filter(e => e.id !== entryId);
    } catch (e) {
      console.error(e);
    }
  }

  $effect(() => { if (notebookId) load(); });
</script>

<div class="mx-auto max-w-3xl space-y-6 p-6">
  <div class="flex items-center gap-3">
    <a href="/notebooks" class="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors">
      <ChevronLeft class="h-4 w-4" /> Notebooks
    </a>
  </div>

  {#if loading}
    <div class="flex justify-center py-16">
      <Loader2 class="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  {:else if notFound}
    <div class="py-16 text-center text-muted-foreground">
      <BookCopy class="mx-auto mb-3 h-10 w-10 opacity-20" />
      <p class="text-sm">Notebook not found.</p>
    </div>
  {:else if notebook}
    <div>
      <h1 class="text-2xl font-semibold">{notebook.name}</h1>
      {#if notebook.description}
        <p class="mt-1 text-sm text-muted-foreground">{notebook.description}</p>
      {/if}
      <p class="mt-1 text-xs text-muted-foreground/60">{entries.length} {entries.length === 1 ? 'entry' : 'entries'}</p>
    </div>

    {#if entries.length === 0}
      <div class="py-16 text-center text-muted-foreground">
        <BookCopy class="mx-auto mb-3 h-10 w-10 opacity-20" />
        <p class="text-sm">No entries yet. Add marginalia from any book to this notebook.</p>
        <p class="mt-1 text-xs text-muted-foreground/60">Open a book, find a marginalium, and use "Add to notebook".</p>
      </div>
    {:else}
      <div class="space-y-6">
        {#each Object.entries(byBook) as [bookIdStr, group]}
          {@const bookId = Number(bookIdStr)}
          <div>
            <a
              href="/book/{bookId}"
              class="flex items-center gap-2 mb-3 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
            >
              <BookOpen class="h-3.5 w-3.5 shrink-0" />
              {group.title}
              <span class="text-xs text-muted-foreground/60">({group.entries.length})</span>
            </a>
            <div class="space-y-2 pl-5 border-l border-muted">
              {#each group.entries as e (e.id)}
                <div class="group rounded-lg border p-3 space-y-1.5 transition-colors hover:bg-muted/30">
                  <div class="flex items-start justify-between gap-2">
                    <div class="flex items-center gap-1.5 flex-wrap">
                      <span class="rounded-full px-2 py-0.5 text-[11px] font-medium {KIND_COLORS[e.kind] ?? 'bg-muted text-muted-foreground'}">
                        {e.kind}
                      </span>
                      {#if e.reading_level}
                        <span class="rounded-full px-2 py-0.5 text-[11px] font-medium {LEVEL_COLORS[e.reading_level] ?? ''}">
                          {e.reading_level}
                        </span>
                      {/if}
                      {#if e.chapter}
                        <span class="text-[11px] text-muted-foreground">{e.chapter}</span>
                      {/if}
                    </div>
                    <button
                      onclick={() => removeEntry(e.id)}
                      class="invisible group-hover:visible shrink-0 text-muted-foreground/40 hover:text-destructive transition-colors"
                      title="Remove from notebook"
                    >
                      <Trash2 class="h-3.5 w-3.5" />
                    </button>
                  </div>
                  <p class="text-sm leading-relaxed">{e.content}</p>
                  {#if e.note}
                    <p class="text-xs text-muted-foreground italic border-l-2 border-muted pl-2">
                      {e.note}
                    </p>
                  {/if}
                  <p class="text-[11px] text-muted-foreground/50">
                    {new Date(e.created_at).toLocaleDateString()}
                  </p>
                </div>
              {/each}
            </div>
          </div>
        {/each}
      </div>
    {/if}
  {/if}
</div>
