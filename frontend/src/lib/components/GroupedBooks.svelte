<script lang="ts">
  import BookGrid from './BookGrid.svelte';
  import { ChevronRight } from 'lucide-svelte';
  import type { Book } from '$lib/types/index';

  interface Props {
    books: Book[];
    groupBy: 'series' | 'year' | 'publisher';
    mode?: 'grid' | 'list';
    search?: string;
    selectionMode?: boolean;
    selectedIds?: Set<number>;
    onToggleSelect?: (id: number) => void;
  }

  let { books, groupBy, mode = 'grid', search = '', selectionMode = false, selectedIds = new Set(), onToggleSelect }: Props = $props();

  // Client-side search filter
  const filtered = $derived.by(() => {
    const q = search.trim().toLowerCase();
    if (!q) return books;
    return books.filter(b =>
      b.title.toLowerCase().includes(q) ||
      b.authors?.some(a => a.name.toLowerCase().includes(q))
    );
  });

  // Group label extractor
  function getKey(book: Book): string {
    if (groupBy === 'series') return book.series?.[0]?.name ?? '(No Series)';
    if (groupBy === 'year') {
      return book.published_date
        ? String(new Date(book.published_date).getFullYear())
        : 'Unknown';
    }
    return book.publisher ?? '(No Publisher)';
  }

  const groups = $derived.by(() => {
    const map = new Map<string, Book[]>();
    for (const book of filtered) {
      const key = getKey(book);
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(book);
    }

    const entries = Array.from(map.entries()).map(([label, items]) => ({ label, items }));

    if (groupBy === 'year') {
      // Descending year, Unknown at end
      entries.sort((a, b) => {
        if (a.label === 'Unknown') return 1;
        if (b.label === 'Unknown') return -1;
        return Number(b.label) - Number(a.label);
      });
    } else {
      // Alphabetical, "(No X)" at end
      entries.sort((a, b) => {
        if (a.label.startsWith('(')) return 1;
        if (b.label.startsWith('(')) return -1;
        return a.label.localeCompare(b.label);
      });
    }

    return entries;
  });

  // Collapsed state — track which group labels are collapsed
  let collapsed = $state(new Set<string>());

  function toggle(label: string) {
    const next = new Set(collapsed);
    if (next.has(label)) next.delete(label);
    else next.add(label);
    collapsed = next;
  }

  const GROUP_LABEL: Record<string, string> = {
    series: 'series',
    year: 'year',
    publisher: 'publisher',
  };
</script>

{#if groups.length === 0}
  <div class="flex flex-col items-center justify-center gap-2 py-16 text-muted-foreground text-sm">
    No books match your search.
  </div>
{:else}
  <div class="space-y-1">
    {#each groups as group (group.label)}
      {@const open = !collapsed.has(group.label)}
      <section>
        <!-- Group header -->
        <button
          onclick={() => toggle(group.label)}
          class="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-muted/50 group"
        >
          <ChevronRight
            class="h-3.5 w-3.5 shrink-0 text-muted-foreground/50 transition-transform duration-150 {open ? 'rotate-90' : ''}"
          />
          <span class="flex-1 text-sm font-semibold tracking-tight">{group.label}</span>
          <span class="text-xs tabular-nums text-muted-foreground/50">
            {group.items.length} {group.items.length === 1 ? 'book' : 'books'}
          </span>
        </button>

        <!-- Group content -->
        {#if open}
          <div class="mt-2 mb-6 pl-5">
            <BookGrid books={group.items} {mode} {selectionMode} {selectedIds} {onToggleSelect} />
          </div>
        {/if}
      </section>
    {/each}
  </div>
{/if}
