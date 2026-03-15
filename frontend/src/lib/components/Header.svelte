<script lang="ts">
  import { goto } from "$app/navigation";
  import { Button } from "$lib/components/ui/button";
  import { Input } from "$lib/components/ui/input";
  import { Search, LogOut, User, Moon, Sun, Menu } from "lucide-svelte";
  import { toggleMode, mode } from "mode-watcher";
  import * as api from "$lib/api/client";

  interface Props {
    onToggleMobile?: () => void;
  }

  let { onToggleMobile }: Props = $props();

  let searchQuery = $state("");
  let userMenuOpen = $state(false);

  let isDark = $derived(mode.current === 'dark');

  async function handleSearch(e: SubmitEvent) {
    e.preventDefault();
    if (searchQuery.trim()) {
      await goto(`/search?q=${encodeURIComponent(searchQuery.trim())}`);
    }
  }

  async function handleLogout() {
    api.logout();
    await goto("/auth/login");
  }
</script>

<!-- pt-safe adds env(safe-area-inset-top) on iOS / Capacitor -->
<header class="sticky top-0 z-30 border-b bg-background/95 backdrop-blur-sm pt-safe">
  <div class="flex h-12 items-center gap-3 px-4 sm:px-5">
  <Button variant="ghost" size="icon" class="md:hidden h-8 w-8" onclick={onToggleMobile}>
    <Menu class="h-4 w-4" />
  </Button>

  <form onsubmit={handleSearch} class="flex flex-1 items-center">
    <div class="relative w-full max-w-sm">
      <Search class="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
      <Input
        type="search"
        placeholder="Search books, authors…"
        bind:value={searchQuery}
        class="h-8 pl-8 text-sm bg-muted/50 border-transparent focus:border-border focus:bg-background"
      />
    </div>
  </form>

  <div class="flex items-center gap-0.5">
    <Button variant="ghost" size="icon" class="h-8 w-8" onclick={toggleMode} title="Toggle theme">
      {#if isDark}
        <Sun class="h-3.5 w-3.5" />
      {:else}
        <Moon class="h-3.5 w-3.5" />
      {/if}
    </Button>

    <div class="relative">
      <Button variant="ghost" size="icon" class="h-8 w-8" onclick={() => (userMenuOpen = !userMenuOpen)}>
        <User class="h-3.5 w-3.5" />
      </Button>

      {#if userMenuOpen}
        <div
          class="absolute right-0 top-full mt-1.5 w-44 rounded-md border bg-popover p-1 shadow-lg"
          role="menu"
        >
          <a
            href="/settings"
            class="flex w-full items-center gap-2 rounded-sm px-3 py-1.5 text-sm text-foreground hover:bg-muted"
          >
            <User class="h-3.5 w-3.5 text-muted-foreground" /> Settings
          </a>
          <button
            onclick={handleLogout}
            class="flex w-full items-center gap-2 rounded-sm px-3 py-1.5 text-sm text-foreground hover:bg-muted"
          >
            <LogOut class="h-3.5 w-3.5 text-muted-foreground" /> Sign out
          </button>
        </div>
      {/if}
    </div>
  </div>
  </div>
</header>
