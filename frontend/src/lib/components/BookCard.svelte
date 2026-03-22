<script lang="ts">
  import { cn } from "$lib/utils/cn";
  import { Badge } from "$lib/components/ui/badge";
  import { BookOpen, Headphones, Check, Eye, BookMarked, CheckCircle, XCircle } from "lucide-svelte";
  import type { Book } from "$lib/types/index";
  import { bookCoverUrl, setBookStatus } from "$lib/api/client";

  interface Props {
    book: Book;
    class?: string;
    selectionMode?: boolean;
    selected?: boolean;
    onToggleSelect?: (id: number) => void;
  }

  let { book, class: className, selectionMode = false, selected = false, onToggleSelect }: Props = $props();

  let coverUrl = $derived(bookCoverUrl(book));
  let primaryAuthor = $derived(book.authors?.[0]?.name ?? null);
  let primaryFormat = $derived(book.files?.[0]?.format ?? null);
  let primarySeries = $derived(book.series?.[0]?.name ?? null);
  let readingStatus = $state(book.reading_status ?? null);
  let statusCycling = $state(false);

  const STATUS_CYCLE: Array<'want_to_read' | 'reading' | 'completed' | null> = [
    null, 'want_to_read', 'reading', 'completed'
  ];

  async function cycleStatus(e: MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (statusCycling) return;

    const currentIdx = STATUS_CYCLE.indexOf(readingStatus as any);
    const nextIdx = (currentIdx + 1) % STATUS_CYCLE.length;
    const nextStatus = STATUS_CYCLE[nextIdx];

    statusCycling = true;
    const prevStatus = readingStatus;
    readingStatus = nextStatus;

    try {
      if (nextStatus) {
        await setBookStatus(book.id, nextStatus);
      } else {
        // Clear status by setting to empty
        await setBookStatus(book.id, '');
      }
      book.reading_status = nextStatus;
    } catch {
      readingStatus = prevStatus;
    } finally {
      statusCycling = false;
    }
  }

  function handleClick(e: MouseEvent) {
    if (selectionMode) {
      e.preventDefault();
      onToggleSelect?.(book.id);
    }
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<a href="/book/{book.id}" class={cn("group block", className)} onclick={handleClick}>
  <div class={cn(
    "overflow-hidden rounded-md border bg-card transition-all duration-150 hover:shadow-sm hover:border-border/80",
    selected && "ring-2 ring-primary border-primary"
  )}>
    <!-- Cover -->
    <div class="relative aspect-2/3 overflow-hidden bg-muted">
      {#if coverUrl}
        <img
          src={coverUrl}
          alt={book.title}
          class="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
          loading="lazy"
        />
      {:else}
        <div class="flex h-full w-full flex-col items-center justify-center gap-3 p-4 bg-muted">
          <BookOpen class="h-8 w-8 text-muted-foreground/40" />
          <p class="text-center font-serif text-xs leading-snug text-muted-foreground/60 line-clamp-3">
            {book.title}
          </p>
        </div>
      {/if}

      {#if selectionMode}
        <button
          class={cn(
            "absolute left-2 top-2 z-10 flex h-5 w-5 items-center justify-center rounded border-2 transition-colors",
            selected ? "border-primary bg-primary text-primary-foreground" : "border-white/80 bg-black/30 text-transparent hover:border-white"
          )}
          onclick={(e) => { e.stopPropagation(); onToggleSelect?.(book.id); }}
        >
          <Check class="h-3 w-3" />
        </button>
      {:else if primaryFormat}
        <span class="absolute left-2 top-2 rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider bg-background/85 text-foreground/70 backdrop-blur-sm">
          {primaryFormat}
        </span>
      {/if}

      {#if book.abs_item_id}
        <span class="absolute right-2 top-2 rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider bg-background/85 text-foreground/70 backdrop-blur-sm flex items-center gap-0.5">
          <Headphones class="h-2.5 w-2.5" />
        </span>
      {/if}

      <!-- Reading status indicator (bottom-right of cover) -->
      {#if !selectionMode}
        <button
          class={cn(
            "absolute bottom-1.5 right-1.5 z-10 flex h-6 w-6 items-center justify-center rounded-full transition-all",
            readingStatus === 'completed' && "bg-emerald-500 text-white shadow-sm",
            readingStatus === 'reading' && "bg-blue-500 text-white shadow-sm",
            readingStatus === 'want_to_read' && "bg-amber-500 text-white shadow-sm",
            !readingStatus && "bg-black/30 text-white/60 opacity-0 group-hover:opacity-100 backdrop-blur-sm",
            statusCycling && "animate-pulse"
          )}
          onclick={cycleStatus}
          title={readingStatus === 'completed' ? 'Completed' : readingStatus === 'reading' ? 'Reading' : readingStatus === 'want_to_read' ? 'Want to read' : 'Set reading status'}
        >
          {#if readingStatus === 'completed'}
            <CheckCircle class="h-3.5 w-3.5" />
          {:else if readingStatus === 'reading'}
            <BookOpen class="h-3.5 w-3.5" />
          {:else if readingStatus === 'want_to_read'}
            <BookMarked class="h-3.5 w-3.5" />
          {:else}
            <Eye class="h-3 w-3" />
          {/if}
        </button>
      {/if}
    </div>

    <!-- Meta -->
    <div class="px-2.5 py-2">
      <h3 class="font-serif line-clamp-2 text-sm leading-snug text-foreground group-hover:text-foreground/80">
        {book.title}
      </h3>
      {#if primaryAuthor}
        <p class="mt-0.5 truncate text-[11px] text-muted-foreground">{primaryAuthor}</p>
      {/if}
      {#if primarySeries}
        <p class="mt-0.5 truncate text-[10px] text-amber-600/80 dark:text-amber-400/70">{primarySeries}</p>
      {/if}
    </div>
  </div>
</a>
