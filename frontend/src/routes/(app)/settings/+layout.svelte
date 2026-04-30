<script lang="ts">
  import { page } from '$app/state';
  import { User as UserIcon, BookOpen, Tag as TagIcon, FileBox, Plug, Cog } from 'lucide-svelte';
  import type { LayoutData } from './$types';

  let { data, children }: { data: LayoutData; children: any } = $props();
  let user = $derived(data.user);

  type SectionId = 'account' | 'library' | 'metadata' | 'files' | 'integrations' | 'system';
  const SECTIONS: { id: SectionId; label: string; icon: any; adminOnly?: boolean }[] = [
    { id: 'account',      label: 'Account',            icon: UserIcon },
    { id: 'library',      label: 'Library',            icon: BookOpen },
    { id: 'metadata',     label: 'Metadata',           icon: TagIcon, adminOnly: true },
    { id: 'files',        label: 'Files & Conversion', icon: FileBox, adminOnly: true },
    { id: 'integrations', label: 'Integrations',       icon: Plug },
    { id: 'system',       label: 'System',             icon: Cog, adminOnly: true },
  ];

  function isActive(id: SectionId): boolean {
    return page.url.pathname === `/settings/${id}` || page.url.pathname.startsWith(`/settings/${id}/`);
  }
</script>

<div class="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
  <div>
    <h1 class="text-3xl font-bold tracking-tight">Settings</h1>
    <p class="mt-1 text-muted-foreground">Manage your Scriptorium instance</p>
  </div>

  <div class="mt-6 flex flex-col gap-6 md:flex-row">
    <!-- Sidebar nav -->
    <nav class="md:sticky md:top-8 md:h-fit md:w-56 md:shrink-0">
      <!-- Mobile: horizontal scroll tabs -->
      <div class="-mx-4 flex gap-1 overflow-x-auto px-4 pb-2 md:hidden">
        {#each SECTIONS as s (s.id)}
          {#if !s.adminOnly || user?.is_admin}
            <a
              href={`/settings/${s.id}`}
              class="shrink-0 rounded-md px-3 py-1.5 text-sm font-medium {isActive(s.id) ? 'bg-accent text-accent-foreground' : 'text-muted-foreground hover:bg-muted'}"
            >
              {s.label}
            </a>
          {/if}
        {/each}
      </div>
      <!-- Desktop: vertical list -->
      <ul class="hidden space-y-1 md:block">
        {#each SECTIONS as s (s.id)}
          {#if !s.adminOnly || user?.is_admin}
            <li>
              <a
                href={`/settings/${s.id}`}
                class="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors {isActive(s.id) ? 'bg-accent text-accent-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground'}"
              >
                <s.icon class="h-4 w-4 shrink-0" />
                {s.label}
              </a>
            </li>
          {/if}
        {/each}
      </ul>
    </nav>

    <!-- Section content -->
    <div class="min-w-0 flex-1 space-y-6">
      {@render children?.()}
    </div>
  </div>
</div>
