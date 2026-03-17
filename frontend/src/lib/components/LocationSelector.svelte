<script lang="ts">
  import { onMount } from "svelte";
  import { MapPin, Plus, ChevronRight } from "lucide-svelte";
  import * as api from "$lib/api/client";
  import type { LocationItem } from "$lib/api/client";

  interface Props {
    value?: number | null;
    onSelect: (locationId: number | null) => void;
    allowCreate?: boolean;
  }

  let { value = null, onSelect, allowCreate = true }: Props = $props();

  let locations = $state<LocationItem[]>([]);
  let loading = $state(true);
  let search = $state('');
  let showDropdown = $state(false);
  let showCreate = $state(false);
  let newName = $state('');
  let newParentId = $state<number | null>(null);
  let creating = $state(false);

  let selectedLocation = $derived(locations.find(l => l.id === value) ?? null);
  let filtered = $derived(
    search.trim()
      ? locations.filter(l => l.tree_path.toLowerCase().includes(search.toLowerCase()))
      : locations
  );

  onMount(async () => {
    try {
      locations = await api.getLocations();
    } catch { /* non-critical */ }
    loading = false;
  });

  function select(loc: LocationItem | null) {
    onSelect(loc?.id ?? null);
    showDropdown = false;
    search = '';
  }

  async function createAndSelect() {
    if (!newName.trim()) return;
    creating = true;
    try {
      const loc = await api.createLocation({
        name: newName.trim(),
        parent_id: newParentId ?? undefined,
      });
      locations = await api.getLocations();
      onSelect(loc.id);
      newName = '';
      newParentId = null;
      showCreate = false;
      showDropdown = false;
    } catch { /* ignore */ }
    creating = false;
  }
</script>

<div class="relative">
  <!-- Selected value / trigger -->
  <button
    type="button"
    onclick={() => showDropdown = !showDropdown}
    class="flex w-full items-center gap-2 rounded-md border bg-background px-3 py-2 text-sm text-left hover:bg-accent/50 transition-colors"
  >
    <MapPin class="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
    {#if selectedLocation}
      <span class="flex-1 truncate">{selectedLocation.tree_path}</span>
    {:else}
      <span class="flex-1 text-muted-foreground">No location set</span>
    {/if}
  </button>

  {#if showDropdown}
    <!-- Backdrop -->
    <div class="fixed inset-0 z-40" onclick={() => { showDropdown = false; search = ''; }}></div>

    <!-- Dropdown -->
    <div class="absolute left-0 top-full z-50 mt-1 w-full min-w-64 rounded-md border bg-popover shadow-md">
      <!-- Search -->
      <div class="border-b p-2">
        <input
          type="text"
          bind:value={search}
          placeholder="Search locations…"
          class="w-full rounded border-none bg-transparent px-2 py-1 text-sm outline-none placeholder:text-muted-foreground/50"
        />
      </div>

      <!-- Options -->
      <div class="max-h-48 overflow-y-auto p-1">
        <!-- None option -->
        <button
          class="w-full rounded-sm px-3 py-1.5 text-left text-sm hover:bg-accent {value === null ? 'font-medium text-primary' : 'text-muted-foreground'}"
          onclick={() => select(null)}
        >
          No location
        </button>

        {#each filtered as loc}
          <button
            class="w-full rounded-sm px-3 py-1.5 text-left text-sm hover:bg-accent {value === loc.id ? 'font-medium text-primary' : ''}"
            onclick={() => select(loc)}
          >
            <span class="block truncate">{loc.tree_path}</span>
          </button>
        {/each}

        {#if filtered.length === 0 && search}
          <p class="px-3 py-2 text-xs text-muted-foreground">No locations match "{search}"</p>
        {/if}
      </div>

      <!-- Create new -->
      {#if allowCreate}
        <div class="border-t p-2">
          {#if showCreate}
            <div class="space-y-2">
              <input
                type="text"
                bind:value={newName}
                placeholder="Location name (e.g. Shelf 3)"
                class="w-full rounded border bg-background px-2 py-1.5 text-sm outline-none focus:ring-1 focus:ring-ring"
                onkeydown={(e) => { if (e.key === 'Enter') createAndSelect(); }}
              />
              <select
                bind:value={newParentId}
                class="w-full rounded border bg-background px-2 py-1.5 text-sm outline-none"
              >
                <option value={null}>No parent (top level)</option>
                {#each locations as loc}
                  <option value={loc.id}>{loc.tree_path}</option>
                {/each}
              </select>
              <div class="flex gap-1">
                <button
                  onclick={createAndSelect}
                  disabled={creating || !newName.trim()}
                  class="flex-1 rounded bg-primary px-2 py-1 text-xs text-primary-foreground disabled:opacity-50"
                >
                  {creating ? 'Creating…' : 'Create'}
                </button>
                <button
                  onclick={() => showCreate = false}
                  class="rounded border px-2 py-1 text-xs hover:bg-accent"
                >
                  Cancel
                </button>
              </div>
            </div>
          {:else}
            <button
              onclick={() => showCreate = true}
              class="flex w-full items-center gap-1.5 rounded-sm px-2 py-1.5 text-xs text-muted-foreground hover:text-foreground hover:bg-accent"
            >
              <Plus class="h-3 w-3" /> New location
            </button>
          {/if}
        </div>
      {/if}
    </div>
  {/if}
</div>
