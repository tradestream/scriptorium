<script lang="ts">
  import { toastStore } from '$lib/stores/toasts.svelte';
  import { X } from 'lucide-svelte';

  const variantClass: Record<string, string> = {
    default: 'bg-card border text-card-foreground',
    success: 'bg-green-600 text-white border-green-700',
    error: 'bg-destructive text-destructive-foreground border-destructive',
  };
</script>

<div class="pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col gap-2">
  {#each toastStore.items as toast (toast.id)}
    <div
      class="pointer-events-auto flex min-w-64 max-w-sm items-start gap-2 rounded-lg border px-4 py-3 shadow-lg {variantClass[toast.variant] ?? variantClass.default}"
    >
      <p class="flex-1 text-sm">{toast.message}</p>
      <button
        onclick={() => toastStore.remove(toast.id)}
        class="mt-0.5 shrink-0 opacity-70 hover:opacity-100"
        aria-label="Dismiss"
      >
        <X class="h-3.5 w-3.5" />
      </button>
    </div>
  {/each}
</div>
