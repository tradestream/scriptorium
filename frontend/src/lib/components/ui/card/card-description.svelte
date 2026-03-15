<script lang="ts">
  import { cn } from "$lib/utils/cn";
  import type { Snippet } from "svelte";

  interface Props { children?: Snippet; class?: string; }
  let { children, class: className }: Props = $props();
</script>

<p class={cn("text-sm text-muted-foreground", className)}>
  {#if children}{@render children()}{/if}
</p>
