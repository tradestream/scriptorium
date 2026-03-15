<script lang="ts">
  import { Card, CardContent, CardHeader, CardTitle } from "$lib/components/ui/card";
  import { Button } from "$lib/components/ui/button";
  import { Input } from "$lib/components/ui/input";
  import { Badge } from "$lib/components/ui/badge";
  import { Separator } from "$lib/components/ui/separator";
  import { BookMarked, Plus, Pencil, Trash2, Sparkles, X } from "lucide-svelte";
  import * as api from "$lib/api/client";
  import type { Shelf, SmartFilterRule } from "$lib/types/index";
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();

  let shelves = $state<Shelf[]>(data.shelves ?? []);
  let loading = $state(false);

  // Dialog state
  let showDialog = $state(false);
  let editingShelf = $state<Shelf | null>(null);

  // Form fields
  let formName = $state('');
  let formDescription = $state('');
  let formIsSmart = $state(false);
  let formRules = $state<SmartFilterRule[]>([]);
  let saving = $state(false);
  let formError = $state('');

  // New rule inputs
  let newRuleField = $state<SmartFilterRule['field']>('tag');
  let newRuleValue = $state('');

  const FIELDS: { value: SmartFilterRule['field']; label: string; inputType?: 'text' | 'status' | 'rating' }[] = [
    { value: 'tag', label: 'Tag contains' },
    { value: 'author', label: 'Author contains' },
    { value: 'series', label: 'Series contains' },
    { value: 'title', label: 'Title contains' },
    { value: 'language', label: 'Language' },
    { value: 'status', label: 'Reading status', inputType: 'status' },
    { value: 'rating', label: 'Rating equals', inputType: 'rating' },
    { value: 'min_rating', label: 'Rating at least', inputType: 'rating' },
  ];

  const STATUS_VALUES = [
    { value: 'want_to_read', label: 'Want to Read' },
    { value: 'reading', label: 'Reading' },
    { value: 'completed', label: 'Completed' },
    { value: 'abandoned', label: 'Abandoned' },
  ];

  let currentFieldDef = $derived(FIELDS.find(f => f.value === newRuleField));

  function fieldLabel(rule: SmartFilterRule): string {
    return FIELDS.find(f => f.value === rule.field)?.label ?? rule.field;
  }

  function ruleValueLabel(rule: SmartFilterRule): string {
    if (rule.field === 'status') {
      return STATUS_VALUES.find(s => s.value === rule.value)?.label ?? rule.value;
    }
    if (rule.field === 'rating' || rule.field === 'min_rating') {
      return '★'.repeat(Number(rule.value));
    }
    return `"${rule.value}"`;
  }

  async function loadShelves() {
    loading = true;
    try {
      shelves = await api.getShelves();
    } catch { /* ignore */ } finally {
      loading = false;
    }
  }

  function openCreate() {
    editingShelf = null;
    formName = '';
    formDescription = '';
    formIsSmart = false;
    formRules = [];
    formError = '';
    newRuleValue = '';
    showDialog = true;
  }

  function openEdit(shelf: Shelf) {
    editingShelf = shelf;
    formName = shelf.name;
    formDescription = shelf.description ?? '';
    formIsSmart = shelf.is_smart;
    try {
      formRules = shelf.smart_filter ? JSON.parse(shelf.smart_filter) : [];
      if (!Array.isArray(formRules)) formRules = [formRules];
    } catch {
      formRules = [];
    }
    formError = '';
    newRuleValue = '';
    showDialog = true;
  }

  function closeDialog() {
    showDialog = false;
  }

  function addRule() {
    const v = newRuleValue.trim();
    if (!v) return;
    const op: SmartFilterRule['op'] =
      newRuleField === 'status' ? 'equals' :
      newRuleField === 'rating' || newRuleField === 'min_rating' ? 'gte' :
      'contains';
    formRules = [...formRules, { field: newRuleField, op, value: v }];
    newRuleValue = '';
  }

  function removeRule(index: number) {
    formRules = formRules.filter((_, i) => i !== index);
  }

  async function saveShelf() {
    if (!formName.trim()) { formError = 'Name is required'; return; }
    saving = true;
    formError = '';
    try {
      const payload = {
        name: formName.trim(),
        description: formDescription.trim() || null,
        is_smart: formIsSmart,
        smart_filter: formIsSmart && formRules.length > 0 ? JSON.stringify(formRules) : null,
      };
      if (editingShelf) {
        await api.updateShelf(editingShelf.id, payload);
      } else {
        await api.createShelf(payload);
      }
      showDialog = false;
      await loadShelves();
    } catch (err) {
      formError = err instanceof Error ? err.message : 'Save failed';
    } finally {
      saving = false;
    }
  }

  async function deleteShelf(shelf: Shelf) {
    if (!confirm(`Delete shelf "${shelf.name}"?`)) return;
    try {
      await api.deleteShelf(shelf.id);
      await loadShelves();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Delete failed');
    }
  }
</script>

<div class="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
  <div class="mb-6 flex items-center justify-between">
    <div>
      <h1 class="text-3xl font-bold tracking-tight">Shelves</h1>
      <p class="mt-1 text-muted-foreground">Group your books into named lists for quick access</p>
    </div>
    <Button onclick={openCreate}>
      <Plus class="mr-2 h-4 w-4" /> New Shelf
    </Button>
  </div>

  {#if loading}
    <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {#each [1,2,3] as _}
        <Card class="animate-pulse">
          <CardHeader><div class="h-5 w-1/2 rounded bg-muted"></div></CardHeader>
          <CardContent><div class="h-4 w-1/3 rounded bg-muted"></div></CardContent>
        </Card>
      {/each}
    </div>
  {:else if shelves.length > 0}
    <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {#each shelves as shelf}
        <Card class="transition-shadow hover:shadow-md">
          <CardHeader class="flex flex-row items-start justify-between pb-2">
            <div class="flex-1">
              <a href="/shelves/{shelf.id}" class="hover:underline">
                <CardTitle class="text-lg">{shelf.name}</CardTitle>
              </a>
              {#if shelf.is_smart}
                <Badge variant="secondary" class="mt-1 text-xs">
                  <Sparkles class="mr-1 h-3 w-3" />Smart
                </Badge>
              {/if}
            </div>
            <div class="flex gap-1">
              <Button variant="ghost" size="icon" class="h-7 w-7" onclick={() => openEdit(shelf)}>
                <Pencil class="h-3.5 w-3.5" />
              </Button>
              <Button variant="ghost" size="icon" class="h-7 w-7 text-destructive hover:text-destructive" onclick={() => deleteShelf(shelf)}>
                <Trash2 class="h-3.5 w-3.5" />
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {#if shelf.description}
              <p class="text-sm text-muted-foreground">{shelf.description}</p>
            {/if}
            <p class="mt-1 text-sm text-muted-foreground">{shelf.book_count ?? 0} books</p>
          </CardContent>
        </Card>
      {/each}
    </div>
  {:else}
    <Card class="py-12 text-center">
      <CardContent>
        <BookMarked class="mx-auto h-12 w-12 text-muted-foreground" />
        <p class="mt-4 text-muted-foreground">No shelves yet. Create one to organize your books.</p>
        <Button class="mt-4" onclick={openCreate}>
          <Plus class="mr-2 h-4 w-4" /> Create Shelf
        </Button>
      </CardContent>
    </Card>
  {/if}
</div>

<!-- Create / Edit dialog -->
{#if showDialog}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" role="dialog" aria-modal="true">
    <div class="mx-4 w-full max-w-lg rounded-lg border bg-background p-6 shadow-xl">
      <div class="mb-4 flex items-center justify-between">
        <h2 class="text-lg font-semibold">{editingShelf ? 'Edit Shelf' : 'New Shelf'}</h2>
        <Button variant="ghost" size="icon" onclick={closeDialog}><X class="h-4 w-4" /></Button>
      </div>

      <div class="space-y-4">
        <div class="space-y-1.5">
          <label class="text-sm font-medium" for="shelf-name">Name</label>
          <Input id="shelf-name" bind:value={formName} placeholder="My shelf..." />
        </div>

        <div class="space-y-1.5">
          <label class="text-sm font-medium" for="shelf-desc">Description (optional)</label>
          <Input id="shelf-desc" bind:value={formDescription} placeholder="What's on this shelf?" />
        </div>

        <div class="flex items-center gap-3">
          <input
            type="checkbox"
            id="shelf-smart"
            bind:checked={formIsSmart}
            class="h-4 w-4 rounded border"
          />
          <label for="shelf-smart" class="flex items-center gap-1.5 text-sm font-medium cursor-pointer">
            <Sparkles class="h-4 w-4 text-muted-foreground" />
            Smart shelf (auto-populated by rules)
          </label>
        </div>

        {#if formIsSmart}
          <Separator />
          <div class="space-y-3">
            <p class="text-sm font-medium">Filter Rules</p>
            <p class="text-xs text-muted-foreground">Books matching ALL rules are included automatically.</p>

            {#if formRules.length > 0}
              <div class="space-y-2">
                {#each formRules as rule, i}
                  <div class="flex items-center gap-2 rounded-md border bg-muted/50 px-3 py-2 text-sm">
                    <span class="font-medium">{fieldLabel(rule)}</span>
                    <span class="flex-1 text-xs">{ruleValueLabel(rule)}</span>
                    <Button variant="ghost" size="icon" class="h-6 w-6" onclick={() => removeRule(i)}>
                      <X class="h-3 w-3" />
                    </Button>
                  </div>
                {/each}
              </div>
            {/if}

            <div class="flex gap-2">
              <select
                bind:value={newRuleField}
                onchange={() => { newRuleValue = ''; }}
                class="rounded-md border bg-background px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                {#each FIELDS as f}
                  <option value={f.value}>{f.label}</option>
                {/each}
              </select>
              {#if currentFieldDef?.inputType === 'status'}
                <select
                  bind:value={newRuleValue}
                  class="flex-1 rounded-md border bg-background px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="">Select status...</option>
                  {#each STATUS_VALUES as s}
                    <option value={s.value}>{s.label}</option>
                  {/each}
                </select>
              {:else if currentFieldDef?.inputType === 'rating'}
                <select
                  bind:value={newRuleValue}
                  class="flex-1 rounded-md border bg-background px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="">Select rating...</option>
                  {#each [1, 2, 3, 4, 5] as n}
                    <option value={String(n)}>{'★'.repeat(n)} ({n} star{n > 1 ? 's' : ''})</option>
                  {/each}
                </select>
              {:else}
                <Input
                  bind:value={newRuleValue}
                  placeholder="value..."
                  class="flex-1"
                  onkeydown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addRule(); } }}
                />
              {/if}
              <Button variant="outline" size="sm" onclick={addRule} disabled={!newRuleValue.trim()}>
                <Plus class="h-4 w-4" />
              </Button>
            </div>
          </div>
        {/if}

        {#if formError}
          <p class="text-sm text-destructive">{formError}</p>
        {/if}

        <div class="flex justify-end gap-2 pt-2">
          <Button variant="outline" onclick={closeDialog} disabled={saving}>Cancel</Button>
          <Button onclick={saveShelf} disabled={saving}>
            {saving ? 'Saving...' : editingShelf ? 'Save Changes' : 'Create Shelf'}
          </Button>
        </div>
      </div>
    </div>
  </div>
{/if}
