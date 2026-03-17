<script lang="ts">
  import { page } from "$app/state";
  import { cn } from "$lib/utils/cn";
  import { Separator } from "$lib/components/ui/separator";
  import {
    Home,
    Search,
    BookOpen,
    Library,
    Settings,
    BookMarked,
    FolderOpen,
    PanelLeftClose,
    PanelLeft,
    EyeOff,
    Users,
    Tag,
    Layers,
    BarChart2,
    Copy,
    MessageSquare,
    Database,
    Feather,
    BookCopy,
    Inbox,
    BookPlus,
    Headphones,
    Newspaper,
  } from "lucide-svelte";
  import type { Library as LibraryType, Shelf, Collection } from "$lib/types/index";
  import { DragDropProvider } from "@dnd-kit-svelte/svelte";
  import { move } from "@dnd-kit/helpers";
  import * as api from "$lib/api/client";
  import SortableLibraryItem from "./SortableLibraryItem.svelte";

  interface Props {
    libraries?: LibraryType[];
    shelves?: Shelf[];
    pinnedCollections?: Collection[];
    collapsed?: boolean;
  }

  let { libraries = [], shelves = [], pinnedCollections = [], collapsed = $bindable(false) }: Props = $props();

  // Local sortable copy — updated optimistically on drag
  let sortedLibraries = $state<LibraryType[]>([]);
  $effect(() => {
    sortedLibraries = [...libraries];
  });

  const navItems = [
    { label: "Home",           href: "/",                  icon: Home },
    { label: "Add Book",       href: "/add",               icon: BookPlus },
    { label: "Search",         href: "/search",            icon: Search },
    { label: "Authors",        href: "/browse/authors",    icon: Users },
    { label: "Tags",           href: "/browse/tags",       icon: Tag },
    { label: "Series",         href: "/browse/series",     icon: Layers },
    { label: "Audiobooks",     href: "/browse/audiobooks", icon: Headphones },
    { label: "Articles",       href: "/articles",          icon: Newspaper },
    { label: "Shelves",        href: "/shelves",           icon: BookMarked },
    { label: "Collections",    href: "/collections",       icon: Layers },
    { label: "Duplicates",     href: "/duplicates",        icon: Copy },
    { label: "Metadata",       href: "/metadata",          icon: Database },
    { label: "Stats",          href: "/stats",             icon: BarChart2 },
    { label: "Notes",          href: "/annotations",       icon: MessageSquare },
    { label: "Marginalia",     href: "/marginalia",        icon: Feather },
    { label: "Notebooks",      href: "/notebooks",         icon: BookCopy },
    { label: "Loose Leaves",   href: "/loose-leaves",      icon: Inbox },
    { label: "Settings",       href: "/settings",          icon: Settings },
  ];

  function isActive(href: string): boolean {
    if (href === "/") return page.url.pathname === "/";
    return page.url.pathname.startsWith(href);
  }

  async function saveOrder() {
    try {
      await api.reorderLibraries(sortedLibraries.map(l => l.id));
    } catch {
      // Revert on failure
      sortedLibraries = [...libraries];
    }
  }
</script>

<aside
  class={cn(
    "flex h-full flex-col border-r bg-sidebar text-sidebar-foreground transition-all duration-200",
    collapsed ? "w-14" : "w-56"
  )}
>
  <!-- Wordmark -->
  <div class={cn(
    "flex h-14 items-center gap-2 border-b px-3",
    collapsed && "justify-center px-0"
  )}>
    {#if collapsed}
      <button
        onclick={() => (collapsed = false)}
        class="flex h-8 w-8 items-center justify-center rounded-md text-sidebar-foreground/60 hover:bg-sidebar-foreground/8 hover:text-sidebar-foreground transition-colors"
        title="Expand sidebar"
      >
        <PanelLeft class="h-4 w-4" />
      </button>
    {:else}
      <a href="/" class="flex min-w-0 flex-1 items-center gap-2">
        <BookOpen class="h-4 w-4 shrink-0 text-sidebar-foreground/50" />
        <span class="font-serif text-base font-semibold tracking-tight truncate">Scriptorium</span>
      </a>
      <button
        onclick={() => (collapsed = true)}
        class="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-sidebar-foreground/35 hover:bg-sidebar-foreground/8 hover:text-sidebar-foreground transition-colors"
        title="Collapse sidebar"
      >
        <PanelLeftClose class="h-3.5 w-3.5" />
      </button>
    {/if}
  </div>

  <!-- Nav -->
  <nav class="flex-1 overflow-y-auto px-2 py-3 space-y-0.5">
    {#each navItems as item}
      {@const Icon = item.icon}
      {@const active = isActive(item.href)}
      <a
        href={item.href}
        title={collapsed ? item.label : undefined}
        class={cn(
          "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm transition-colors",
          active
            ? "bg-sidebar-foreground/10 text-sidebar-foreground font-medium"
            : "text-sidebar-foreground/55 hover:bg-sidebar-foreground/6 hover:text-sidebar-foreground",
          collapsed && "justify-center px-0 h-9 w-9 mx-auto"
        )}
      >
        <Icon class="h-3.5 w-3.5 shrink-0" />
        {#if !collapsed}
          <span class="truncate">{item.label}</span>
          {#if active}
            <span class="ml-auto h-1.5 w-1.5 rounded-full bg-amber-500 shrink-0"></span>
          {/if}
        {/if}
      </a>
    {/each}

    {#if sortedLibraries.length > 0}
      <div class="pt-4">
        {#if !collapsed}
          <p class="mb-1 px-2.5 text-[10px] font-semibold uppercase tracking-widest text-sidebar-foreground/35">
            Libraries
          </p>
        {:else}
          <Separator class="my-2 bg-sidebar-foreground/10" />
        {/if}

        {#if collapsed}
          {#each sortedLibraries as lib}
            <a
              href="/library/{lib.id}"
              title={lib.name}
              class={cn(
                "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm transition-colors",
                lib.is_hidden ? "opacity-40" : "",
                page.url.pathname === `/library/${lib.id}`
                  ? "bg-sidebar-foreground/10 text-sidebar-foreground font-medium"
                  : "text-sidebar-foreground/55 hover:bg-sidebar-foreground/6 hover:text-sidebar-foreground",
                "justify-center px-0 h-9 w-9 mx-auto"
              )}
            >
              <Library class="h-3.5 w-3.5 shrink-0" />
            </a>
          {/each}
        {:else}
          <DragDropProvider
            onDragOver={(event) => { sortedLibraries = move(sortedLibraries, event as any); }}
            onDragEnd={saveOrder}
          >
            {#each sortedLibraries as lib, index (lib.id)}
              <SortableLibraryItem
                {lib}
                {index}
                active={page.url.pathname === `/library/${lib.id}`}
              />
            {/each}
          </DragDropProvider>
        {/if}
      </div>
    {/if}

    {#if shelves.length > 0}
      <div class="pt-4">
        {#if !collapsed}
          <p class="mb-1 px-2.5 text-[10px] font-semibold uppercase tracking-widest text-sidebar-foreground/35">
            Shelves
          </p>
        {:else}
          <Separator class="my-2 bg-sidebar-foreground/10" />
        {/if}
        {#each shelves as shelf}
          <a
            href="/shelves/{shelf.id}"
            title={collapsed ? shelf.name : undefined}
            class={cn(
              "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm text-sidebar-foreground/55 transition-colors hover:bg-sidebar-foreground/6 hover:text-sidebar-foreground",
              collapsed && "justify-center px-0 h-9 w-9 mx-auto"
            )}
          >
            <FolderOpen class="h-3.5 w-3.5 shrink-0" />
            {#if !collapsed}
              <span class="truncate">{shelf.name}</span>
            {/if}
          </a>
        {/each}
      </div>
    {/if}

    {#if pinnedCollections.length > 0}
      <div class="pt-4">
        {#if !collapsed}
          <p class="mb-1 px-2.5 text-[10px] font-semibold uppercase tracking-widest text-sidebar-foreground/35">
            Collections
          </p>
        {:else}
          <Separator class="my-2 bg-sidebar-foreground/10" />
        {/if}
        {#each pinnedCollections as col}
          <a
            href="/collections/{col.id}"
            title={collapsed ? col.name : undefined}
            class={cn(
              "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm text-sidebar-foreground/55 transition-colors hover:bg-sidebar-foreground/6 hover:text-sidebar-foreground",
              collapsed && "justify-center px-0 h-9 w-9 mx-auto",
              col.is_smart && "italic"
            )}
          >
            <Layers class="h-3.5 w-3.5 shrink-0" />
            {#if !collapsed}
              <span class="truncate">{col.name}</span>
            {/if}
          </a>
        {/each}
      </div>
    {/if}
  </nav>
</aside>
