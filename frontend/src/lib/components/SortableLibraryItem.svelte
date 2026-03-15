<script lang="ts">
  import { cn } from "$lib/utils/cn";
  import { Library, EyeOff, GripVertical } from "lucide-svelte";
  import type { Library as LibraryType } from "$lib/types/index";
  import { useSortable } from "@dnd-kit-svelte/svelte/sortable";

  interface Props {
    lib: LibraryType;
    index: number;
    active: boolean;
  }

  let { lib, index, active }: Props = $props();

  const { ref, handleRef, isDragging } = useSortable({
    id: () => lib.id,
    index: () => index,
    feedback: 'move',
  });
</script>

<div
  {@attach ref}
  class={cn(
    "group flex items-center gap-1.5 rounded-md py-1.5 text-sm transition-colors",
    lib.is_hidden ? "opacity-40" : "",
    active
      ? "bg-sidebar-foreground/10 text-sidebar-foreground font-medium"
      : "text-sidebar-foreground/55 hover:bg-sidebar-foreground/6 hover:text-sidebar-foreground",
    isDragging.current && "opacity-30"
  )}
>
  <button
    {@attach handleRef}
    class="ml-1 shrink-0 cursor-grab active:cursor-grabbing opacity-0 group-hover:opacity-60 transition-opacity touch-none"
    aria-label="Drag to reorder {lib.name}"
    onclick={(e) => e.preventDefault()}
  >
    <GripVertical class="h-3 w-3" />
  </button>
  <a href="/library/{lib.id}" class="flex min-w-0 flex-1 items-center gap-2 pr-2.5">
    <Library class="h-3.5 w-3.5 shrink-0" />
    <span class="truncate">{lib.name}</span>
    <span class="ml-auto flex items-center gap-1 shrink-0">
      {#if lib.is_hidden}
        <EyeOff class="h-3 w-3 text-sidebar-foreground/30" />
      {/if}
      {#if lib.book_count}
        <span class="text-[10px] tabular-nums text-sidebar-foreground/35">{lib.book_count}</span>
      {/if}
    </span>
  </a>
</div>
