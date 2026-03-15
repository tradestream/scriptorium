<script lang="ts">
  import { cn } from "$lib/utils/cn";
  import type { Snippet } from "svelte";

  interface Props { children?: Snippet; class?: string; }
  let { children, class: className }: Props = $props();
</script>

<h3 class={cn("font-semibold leading-none tracking-tight", className)}>
  {#if children}{@render children()}{/if}
</h3>
