<script lang="ts">
  import "../app.css";
  import { ModeWatcher } from "mode-watcher";
  import { onMount } from "svelte";
  import Header from "$lib/components/Header.svelte";
  import Sidebar from "$lib/components/Sidebar.svelte";
  import Toaster from "$lib/components/Toaster.svelte";
  import { startEventClient, stopEventClient } from "$lib/stores/events";
  import ServerSetup from "$lib/components/ServerSetup.svelte";
  import { invalidateAll } from "$app/navigation";
  import type { LayoutData } from './$types';

  let { children, data }: { children: any; data: LayoutData } = $props();

  let sidebarCollapsed = $state(false);
  let mobileOpen = $state(false);

  let user = $derived(data?.user ?? null);
  let libraries = $derived(data?.libraries ?? []);
  let shelves = $derived(data?.shelves ?? []);

  onMount(() => {
    if (user) {
      startEventClient();
      return () => stopEventClient();
    }
  });

  async function onServerSetupComplete() {
    await invalidateAll();
  }
</script>

<ModeWatcher defaultMode="light" />
<Toaster />

{#if data.needsServerSetup}
  <ServerSetup onComplete={onServerSetupComplete} />
{:else if !user}
  {@render children()}
{:else}
  <div class="flex h-screen overflow-hidden">
    <!-- Desktop sidebar -->
    <div class="hidden md:flex">
      <Sidebar {libraries} {shelves} bind:collapsed={sidebarCollapsed} />
    </div>

    <!-- Mobile sidebar overlay -->
    {#if mobileOpen}
      <div class="fixed inset-0 z-40 md:hidden">
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div class="absolute inset-0 bg-background/80 backdrop-blur-sm" onclick={() => (mobileOpen = false)}></div>
        <div class="relative z-50 h-full w-64">
          <Sidebar {libraries} {shelves} />
        </div>
      </div>
    {/if}

    <div class="flex flex-1 flex-col overflow-hidden">
      <Header onToggleMobile={() => (mobileOpen = !mobileOpen)} />
      <main class="flex-1 overflow-y-auto pb-safe">
        {@render children()}
      </main>
    </div>
  </div>
{/if}
