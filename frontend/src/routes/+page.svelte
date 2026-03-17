<script lang="ts">
  import BookGrid from "$lib/components/BookGrid.svelte";
  import { BookOpen, BookMarked, CheckSquare, Library, Clock } from "lucide-svelte";
  // Animation imports removed — motion-sv doesn't work in Capacitor static build
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();

  let stats    = $derived(data.stats);
  let recent   = $derived(data.recent ?? []);
  let reading  = $derived(stats?.currently_reading ?? []);
  let finished = $derived(stats?.recently_completed ?? []);

  function formatTime(seconds: number): string {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
  }

  function timeAgo(iso: string | null): string {
    if (!iso) return 'Never';
    const diff = Date.now() - new Date(iso).getTime();
    const d = Math.floor(diff / 86400000);
    if (d === 0) return 'Today';
    if (d === 1) return 'Yesterday';
    if (d < 7) return `${d}d ago`;
    if (d < 30) return `${Math.floor(d / 7)}w ago`;
    return `${Math.floor(d / 30)}mo ago`;
  }
</script>

<div class="mx-auto max-w-6xl px-6 py-8 space-y-10">

  <!-- Page header -->
  <div class="border-b pb-6">
    <h1 class="font-serif text-3xl font-semibold tracking-tight text-foreground">Library</h1>
    <p class="mt-1 text-sm text-muted-foreground">Your personal reading collection</p>
  </div>

  <!-- Stat cards -->
  <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
    <div class="rounded-lg border bg-card p-4">
      <div class="flex items-start justify-between">
        <p class="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">Total</p>
        <Library class="h-3.5 w-3.5 text-muted-foreground/40 mt-0.5" />
      </div>
      <p class="mt-3 font-serif text-3xl font-semibold tabular-nums text-foreground">
        {stats?.total_books ?? '—'}
      </p>
      <p class="mt-1 text-xs text-muted-foreground">books in library</p>
    </div>

    <div class="rounded-lg border bg-card p-4">
      <div class="flex items-start justify-between">
        <p class="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">Reading</p>
        <BookOpen class="h-3.5 w-3.5 text-muted-foreground/40 mt-0.5" />
      </div>
      <p class="mt-3 font-serif text-3xl font-semibold tabular-nums text-foreground">
        {stats?.books_reading ?? '—'}
      </p>
      <p class="mt-1 text-xs text-muted-foreground">in progress</p>
    </div>

    <div class="rounded-lg border bg-card p-4">
      <div class="flex items-start justify-between">
        <p class="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">Finished</p>
        <CheckSquare class="h-3.5 w-3.5 text-muted-foreground/40 mt-0.5" />
      </div>
      <p class="mt-3 font-serif text-3xl font-semibold tabular-nums text-foreground">
        {stats?.books_completed ?? '—'}
      </p>
      <p class="mt-1 text-xs text-muted-foreground">completed</p>
    </div>

    <div class="rounded-lg border bg-card p-4">
        <div class="flex items-start justify-between">
          <p class="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">Time Read</p>
          <Clock class="h-3.5 w-3.5 text-muted-foreground/40 mt-0.5" />
        </div>
        <p class="mt-3 font-serif text-3xl font-semibold tabular-nums text-foreground">
          {stats ? formatTime(stats.time_reading_seconds) : '—'}
        </p>
        <p class="mt-1 text-xs text-muted-foreground">total reading time</p>
      </div>
  </div>

  <!-- Continue Reading -->
  {#if reading.length > 0}
    <section>
      <div class="mb-4 flex items-baseline gap-2">
        <h2 class="font-serif text-xl font-semibold text-foreground">Continue Reading</h2>
        <span class="text-xs text-muted-foreground">{reading.length} in progress</span>
      </div>
      <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {#each reading as book (book.id)}
          <a
            href="/book/{book.id}"
            class="group flex gap-3.5 rounded-lg border bg-card p-4 transition-colors hover:border-border/60 hover:shadow-sm"
          >
            <div class="mt-0.5 h-full w-0.5 shrink-0 rounded-full bg-amber-400/50 group-hover:bg-amber-400 transition-colors"></div>
            <div class="min-w-0 flex-1">
              <p class="font-serif text-sm font-medium leading-snug text-foreground line-clamp-2">
                {book.title}
              </p>
              {#if book.author}
                <p class="mt-0.5 text-xs text-muted-foreground truncate">{book.author}</p>
              {/if}
              <div class="mt-3 space-y-1.5">
                <div class="h-1 w-full rounded-full bg-muted overflow-hidden">
                  <div class="h-full rounded-full bg-amber-500/60 transition-all" style="width: {book.percentage}%"></div>
                </div>
                <div class="flex items-center justify-between">
                  <span class="text-[10px] tabular-nums text-muted-foreground">{Math.round(book.percentage)}%</span>
                  <span class="text-[10px] text-muted-foreground">{timeAgo(book.last_opened)}</span>
                </div>
              </div>
            </div>
          </a>
        {/each}
      </div>
    </section>
  {/if}

  <!-- Recently Added -->
  <section>
    <div class="mb-5 flex items-baseline justify-between">
      <div class="flex items-baseline gap-2">
        <h2 class="font-serif text-xl font-semibold text-foreground">Recently Added</h2>
        {#if recent.length > 0}
          <span class="text-xs text-muted-foreground">{recent.length} books</span>
        {/if}
      </div>
      {#if recent.length > 0}
        <a href="/browse" class="text-xs text-muted-foreground underline-offset-4 hover:underline hover:text-foreground transition-colors">
          Browse all
        </a>
      {/if}
    </div>

    {#if recent.length > 0}
      <BookGrid books={recent} />
    {:else}
      <div class="flex flex-col items-center justify-center gap-4 rounded-lg border border-dashed py-16">
        <BookOpen class="h-10 w-10 text-muted-foreground/25" />
        <div class="text-center">
          <p class="text-sm font-medium text-foreground">Your library is empty</p>
          <p class="mt-1 text-xs text-muted-foreground">Add a library in Settings to start importing books.</p>
        </div>
        <a
          href="/settings"
          class="mt-1 rounded-md bg-foreground px-4 py-1.5 text-xs font-medium text-background hover:bg-foreground/90 transition-colors"
        >
          Go to Settings
        </a>
      </div>
    {/if}
  </section>

  <!-- Recently Finished -->
  {#if finished.length > 0}
    <section>
      <div class="mb-4 flex items-baseline gap-2">
        <h2 class="font-serif text-xl font-semibold text-foreground">Recently Finished</h2>
        <span class="text-xs text-muted-foreground">{finished.length} books</span>
      </div>
      <div class="divide-y rounded-lg border bg-card overflow-hidden">
        {#each finished.slice(0, 6) as book (book.id)}
          <a
            href="/book/{book.id}"
            class="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-muted/40"
          >
            <BookMarked class="h-3.5 w-3.5 shrink-0 text-amber-500/60" />
            <div class="min-w-0 flex-1">
              <p class="font-serif text-sm text-foreground truncate">{book.title}</p>
              {#if book.author}
                <p class="text-[11px] text-muted-foreground">{book.author}</p>
              {/if}
            </div>
            {#if book.completed_at}
              <span class="shrink-0 text-[11px] tabular-nums text-muted-foreground">{timeAgo(book.completed_at)}</span>
            {/if}
          </a>
        {/each}
      </div>
    </section>
  {/if}

</div>
