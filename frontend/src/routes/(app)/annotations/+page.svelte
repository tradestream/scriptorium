<script lang="ts">
  import { onMount } from 'svelte';
  import { Badge } from '$lib/components/ui/badge';
  import { Button } from '$lib/components/ui/button';
  import { Input } from '$lib/components/ui/input';
  import { Highlighter, MessageSquare, Bookmark, Search, Trash2, ExternalLink } from 'lucide-svelte';
  import * as api from '$lib/api/client';
  import type { AnnotationWithBook } from '$lib/api/client';

  type FilterType = 'all' | 'highlight' | 'note' | 'bookmark';

  let allAnnotations = $state<AnnotationWithBook[]>([]);
  let loading = $state(true);
  let activeFilter = $state<FilterType>('all');
  let searchQuery = $state('');
  let searchDebounce: ReturnType<typeof setTimeout>;

  async function load(type?: string, q?: string) {
    loading = true;
    try {
      allAnnotations = await api.getMyAnnotations(type === 'all' ? undefined : type, q || undefined);
    } catch { /* non-critical */ } finally {
      loading = false;
    }
  }

  onMount(() => load());

  function setFilter(f: FilterType) {
    activeFilter = f;
    load(f, searchQuery);
  }

  function onSearch() {
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(() => load(activeFilter, searchQuery), 300);
  }

  async function remove(id: number) {
    await api.deleteAnnotation(id);
    allAnnotations = allAnnotations.filter(a => a.id !== id);
  }

  // Group annotations by book
  const grouped = $derived(() => {
    const map = new Map<number, { title: string; author: string | null; items: AnnotationWithBook[] }>();
    for (const ann of allAnnotations) {
      if (!map.has(ann.book_id)) {
        map.set(ann.book_id, { title: ann.book_title ?? 'Unknown', author: ann.book_author, items: [] });
      }
      map.get(ann.book_id)!.items.push(ann);
    }
    return [...map.entries()].map(([id, val]) => ({ bookId: id, ...val }));
  });

  const colorClasses: Record<string, string> = {
    yellow: 'bg-yellow-400/80',
    green: 'bg-green-400/80',
    blue: 'bg-blue-400/80',
    pink: 'bg-pink-400/80',
    purple: 'bg-purple-400/80',
  };

  const filters: { value: FilterType; label: string; icon: typeof Highlighter }[] = [
    { value: 'all', label: 'All', icon: MessageSquare },
    { value: 'highlight', label: 'Highlights', icon: Highlighter },
    { value: 'note', label: 'Notes', icon: MessageSquare },
    { value: 'bookmark', label: 'Bookmarks', icon: Bookmark },
  ];
</script>

<div class="mx-auto max-w-3xl px-4 py-8 sm:px-6 lg:px-8">
  <div class="mb-6">
    <h1 class="text-3xl font-bold tracking-tight">Notes & Highlights</h1>
    <p class="mt-1 text-muted-foreground">All your annotations across every book</p>
  </div>

  <!-- Filters + Search -->
  <div class="mb-6 flex flex-wrap items-center gap-3">
    <div class="flex gap-1 rounded-md border p-1">
      {#each filters as f}
        {@const Icon = f.icon}
        <button
          class="flex items-center gap-1.5 rounded px-2.5 py-1 text-sm transition-colors {activeFilter === f.value ? 'bg-muted font-medium text-foreground' : 'text-muted-foreground hover:text-foreground'}"
          onclick={() => setFilter(f.value)}
        >
          <Icon class="h-3.5 w-3.5" />{f.label}
        </button>
      {/each}
    </div>
    <div class="relative flex-1 min-w-48">
      <Search class="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
      <Input
        placeholder="Search notes…"
        bind:value={searchQuery}
        oninput={onSearch}
        class="pl-8 h-9"
      />
    </div>
  </div>

  {#if loading}
    <div class="space-y-4">
      {#each [1, 2, 3] as _}
        <div class="h-24 animate-pulse rounded-lg bg-muted"></div>
      {/each}
    </div>
  {:else if grouped().length === 0}
    <div class="flex flex-col items-center justify-center py-20 text-center">
      <MessageSquare class="h-10 w-10 text-muted-foreground/40" />
      <p class="mt-4 text-sm text-muted-foreground">
        {searchQuery ? 'No annotations match your search.' : 'No annotations yet. Start highlighting and taking notes while reading.'}
      </p>
    </div>
  {:else}
    <div class="space-y-8">
      {#each grouped() as group}
        <div>
          <a
            href="/book/{group.bookId}"
            class="group mb-3 flex items-baseline gap-2 hover:opacity-80"
          >
            <h2 class="text-base font-semibold">{group.title}</h2>
            {#if group.author}
              <span class="text-sm text-muted-foreground">{group.author}</span>
            {/if}
            <ExternalLink class="h-3 w-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
          </a>
          <div class="space-y-2">
            {#each group.items as ann}
              <div class="group/ann flex items-start gap-3 rounded-md border px-3 py-2.5 hover:bg-muted/30 transition-colors">
                <!-- Type indicator -->
                {#if ann.type === 'highlight'}
                  <span class="mt-0.5 h-4 w-1 shrink-0 rounded-full {colorClasses[ann.color ?? 'yellow'] ?? colorClasses.yellow}"></span>
                {:else if ann.type === 'bookmark'}
                  <Bookmark class="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                {:else}
                  <MessageSquare class="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                {/if}

                <div class="min-w-0 flex-1">
                  {#if ann.chapter}
                    <p class="mb-0.5 text-xs text-muted-foreground">{ann.chapter}</p>
                  {/if}
                  {#if ann.content}
                    <p class="text-sm {ann.type === 'highlight' ? 'italic' : ''}">{ann.content}</p>
                  {:else}
                    <p class="text-xs text-muted-foreground italic">Bookmark</p>
                  {/if}
                </div>

                <div class="ml-2 flex shrink-0 items-center gap-2">
                  <span class="text-xs text-muted-foreground">
                    {new Date(ann.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                  </span>
                  <button
                    class="invisible text-muted-foreground/40 hover:text-destructive transition-colors group-hover/ann:visible"
                    onclick={() => remove(ann.id)}
                  >
                    <Trash2 class="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
