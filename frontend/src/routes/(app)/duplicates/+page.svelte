<script lang="ts">
  import { Button } from "$lib/components/ui/button";
  import { Badge } from "$lib/components/ui/badge";
  import { Card, CardContent, CardHeader, CardTitle } from "$lib/components/ui/card";
  import { Copy, RefreshCw, Trash2, CheckCircle } from "lucide-svelte";
  import * as api from "$lib/api/client";
  import type { Book } from "$lib/types/index";

  type DupGroup = Book[];

  let isbnGroups = $state<DupGroup[]>([]);
  let titleGroups = $state<DupGroup[]>([]);
  let loading = $state(false);
  let scanned = $state(false);

  async function scan() {
    loading = true;
    scanned = false;
    try {
      [isbnGroups, titleGroups] = await Promise.all([
        api.findIsbnDuplicates(),
        api.findTitleAuthorDuplicates(),
      ]);
      scanned = true;
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Scan failed');
    } finally {
      loading = false;
    }
  }

  async function deleteBook(bookId: number) {
    if (!confirm('Delete this book from the database? File on disk is NOT deleted.')) return;
    try {
      await api.deleteBook(bookId);
      isbnGroups = isbnGroups.map(g => g.filter(b => b.id !== bookId)).filter(g => g.length > 1);
      titleGroups = titleGroups.map(g => g.filter(b => b.id !== bookId)).filter(g => g.length > 1);
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Delete failed');
    }
  }

  async function consolidate(group: Book[], primaryId: number) {
    const sourceIds = group.map(b => b.id).filter(id => id !== primaryId);
    if (!confirm(`Keep book #${primaryId} and delete ${sourceIds.length} duplicate(s)?`)) return;
    try {
      await api.consolidateDuplicates(primaryId, sourceIds);
      const removeGroup = (groups: Book[][]) => groups.filter(g => !g.some(b => g.includes(b) && group.includes(b)));
      isbnGroups = isbnGroups.filter(g => !group.every(gb => g.find(b => b.id === gb.id)));
      titleGroups = titleGroups.filter(g => !group.every(gb => g.find(b => b.id === gb.id)));
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Consolidation failed');
    }
  }

  const totalDups = $derived(
    new Set([
      ...isbnGroups.flatMap(g => g.map(b => b.id)),
      ...titleGroups.flatMap(g => g.map(b => b.id)),
    ]).size
  );
</script>

<div class="mx-auto max-w-3xl px-4 py-8 sm:px-6 lg:px-8">
  <div class="mb-6 flex items-start justify-between gap-4">
    <div>
      <h1 class="text-3xl font-bold tracking-tight">Duplicate Detection</h1>
      <p class="mt-1 text-muted-foreground">Find books with matching ISBNs or title + author combinations</p>
    </div>
    <Button onclick={scan} disabled={loading} class="shrink-0">
      <RefreshCw class="mr-2 h-4 w-4 {loading ? 'animate-spin' : ''}" />
      {loading ? 'Scanning…' : 'Scan Library'}
    </Button>
  </div>

  {#if scanned && totalDups === 0}
    <div class="flex flex-col items-center justify-center py-16 text-center">
      <CheckCircle class="h-12 w-12 text-green-500" />
      <p class="mt-4 font-medium">No duplicates found</p>
      <p class="mt-1 text-sm text-muted-foreground">Your library looks clean.</p>
    </div>
  {:else if scanned}
    {#if isbnGroups.length > 0}
      <h2 class="mb-3 text-lg font-semibold">ISBN Duplicates ({isbnGroups.length} group{isbnGroups.length !== 1 ? 's' : ''})</h2>
      <div class="mb-6 space-y-3">
        {#each isbnGroups as group}
          <Card>
            <CardHeader class="pb-2">
              <CardTitle class="text-sm text-muted-foreground">ISBN: {group[0].isbn}</CardTitle>
            </CardHeader>
            <CardContent class="space-y-2">
              {#each group as book}
                <div class="flex items-center justify-between gap-2 rounded-md border p-2 text-sm">
                  <div class="min-w-0">
                    <a href="/book/{book.id}" class="font-medium hover:underline truncate block">{book.title}</a>
                    {#if book.authors.length > 0}
                      <span class="text-xs text-muted-foreground">{book.authors.map(a => a.name).join(', ')}</span>
                    {/if}
                    {#if book.files.length > 0}
                      <Badge variant="outline" class="ml-1 text-xs">{book.files[0].format}</Badge>
                    {/if}
                  </div>
                  <div class="flex gap-1">
                    <Button variant="ghost" size="sm" class="h-7 px-2 text-xs" onclick={() => consolidate(group, book.id)} title="Keep this, delete others">Keep</Button>
                    <Button variant="ghost" size="icon" class="h-7 w-7 shrink-0 text-destructive hover:text-destructive" onclick={() => deleteBook(book.id)}>
                      <Trash2 class="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              {/each}
            </CardContent>
          </Card>
        {/each}
      </div>
    {/if}

    {#if titleGroups.length > 0}
      <h2 class="mb-3 text-lg font-semibold">Title + Author Duplicates ({titleGroups.length} group{titleGroups.length !== 1 ? 's' : ''})</h2>
      <div class="space-y-3">
        {#each titleGroups as group}
          <Card>
            <CardContent class="space-y-2 pt-4">
              {#each group as book}
                <div class="flex items-center justify-between gap-2 rounded-md border p-2 text-sm">
                  <div class="min-w-0">
                    <a href="/book/{book.id}" class="font-medium hover:underline truncate block">{book.title}</a>
                    {#if book.authors.length > 0}
                      <span class="text-xs text-muted-foreground">{book.authors.map(a => a.name).join(', ')}</span>
                    {/if}
                    {#if book.files.length > 0}
                      <Badge variant="outline" class="ml-1 text-xs">{book.files[0].format}</Badge>
                    {/if}
                  </div>
                  <div class="flex gap-1">
                    <Button variant="ghost" size="sm" class="h-7 px-2 text-xs" onclick={() => consolidate(group, book.id)} title="Keep this, delete others">Keep</Button>
                    <Button variant="ghost" size="icon" class="h-7 w-7 shrink-0 text-destructive hover:text-destructive" onclick={() => deleteBook(book.id)}>
                      <Trash2 class="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              {/each}
            </CardContent>
          </Card>
        {/each}
      </div>
    {/if}
  {:else}
    <div class="flex flex-col items-center justify-center py-16 text-center">
      <Copy class="h-12 w-12 text-muted-foreground" />
      <p class="mt-4 text-muted-foreground">Click "Scan Library" to find duplicate books.</p>
    </div>
  {/if}
</div>
