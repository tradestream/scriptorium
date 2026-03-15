<script lang="ts">
  import { Badge } from "$lib/components/ui/badge";
  import type { PageData } from './$types';
  let { data }: { data: PageData } = $props();
  let tags = $derived(data.tags);
</script>

<div class="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
  <h1 class="mb-6 text-3xl font-bold tracking-tight">Tags</h1>

  {#if tags.length === 0}
    <p class="py-16 text-center text-muted-foreground">No tags found.</p>
  {:else}
    <div class="flex flex-wrap gap-3">
      {#each tags as tag}
        <a href="/browse/tags/{tag.id}">
          <Badge variant="secondary" class="cursor-pointer px-3 py-1.5 text-sm hover:bg-secondary/80">
            {tag.name}
            <span class="ml-1.5 text-xs text-muted-foreground">{tag.book_count}</span>
          </Badge>
        </a>
      {/each}
    </div>
  {/if}
</div>
