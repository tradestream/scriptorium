<script lang="ts">
  import { Card, CardContent } from "$lib/components/ui/card";
  import { Button } from "$lib/components/ui/button";
  import { Badge } from "$lib/components/ui/badge";
  import { BookMarked, ArrowLeft, Sparkles, Settings } from "lucide-svelte";
  import BookGrid from "$lib/components/BookGrid.svelte";
  import type { PageData } from './$types';
  import type { SmartFilterRule } from '$lib/types/index';

  let { data }: { data: PageData } = $props();
  let shelf = $derived(data.shelf);
  let books = $derived(data.books ?? []);

  let rules = $derived((): SmartFilterRule[] => {
    if (!shelf?.smart_filter) return [];
    try {
      const r = JSON.parse(shelf.smart_filter);
      return Array.isArray(r) ? r : [r];
    } catch {
      return [];
    }
  });

  const STATUS_LABELS: Record<string, string> = {
    want_to_read: 'Want to Read',
    reading: 'Reading',
    completed: 'Completed',
    abandoned: 'Abandoned',
  };

  function ruleLabel(rule: SmartFilterRule): string {
    if (rule.field === 'status') return `Status: ${STATUS_LABELS[rule.value] ?? rule.value}`;
    if (rule.field === 'rating') return `Rating: ${'★'.repeat(Number(rule.value))}`;
    if (rule.field === 'min_rating') return `Rating ≥ ${'★'.repeat(Number(rule.value))}`;
    const labels: Record<string, string> = { tag: 'Tag', author: 'Author', series: 'Series', title: 'Title', language: 'Language' };
    return `${labels[rule.field] ?? rule.field} contains "${rule.value}"`;
  }
</script>

{#if shelf}
  <div class="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
    <div class="mb-6">
      <a href="/shelves" class="mb-4 flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft class="h-4 w-4" /> Back to shelves
      </a>
      <div class="flex items-start justify-between gap-3">
        <div>
          <div class="flex items-center gap-2">
            <h1 class="text-3xl font-bold tracking-tight">{shelf.name}</h1>
            {#if shelf.is_smart}
              <Badge variant="secondary" class="text-xs">
                <Sparkles class="mr-1 h-3 w-3" />Smart
              </Badge>
            {/if}
          </div>
          {#if shelf.description}
            <p class="mt-1 text-muted-foreground">{shelf.description}</p>
          {/if}
          {#if shelf.is_smart && rules().length > 0}
            <div class="mt-2 flex flex-wrap gap-1.5">
              {#each rules() as rule}
                <span class="rounded-full border bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                  {ruleLabel(rule)}
                </span>
              {/each}
            </div>
          {/if}
          <p class="mt-1 text-sm text-muted-foreground">
            {books.length} {shelf.is_smart ? 'matching' : ''} book{books.length !== 1 ? 's' : ''}
          </p>
        </div>
        <Button variant="outline" size="sm" href="/shelves">
          <Settings class="mr-1.5 h-3.5 w-3.5" /> Manage shelves
        </Button>
      </div>
    </div>

    {#if books.length > 0}
      <BookGrid {books} />
    {:else}
      <Card class="py-12 text-center">
        <CardContent>
          <BookMarked class="mx-auto h-12 w-12 text-muted-foreground" />
          <p class="mt-4 text-muted-foreground">
            {shelf.is_smart ? 'No books match the current filter rules.' : 'No books on this shelf yet.'}
          </p>
          {#if !shelf.is_smart}
            <p class="mt-2 text-sm text-muted-foreground">
              Add books from the book detail page.
            </p>
          {/if}
        </CardContent>
      </Card>
    {/if}
  </div>
{:else}
  <div class="flex flex-col items-center justify-center py-16 text-muted-foreground">
    <BookMarked class="h-12 w-12" />
    <p class="mt-4">Shelf not found</p>
    <Button variant="outline" class="mt-4" href="/shelves">Back to shelves</Button>
  </div>
{/if}
