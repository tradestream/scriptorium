<script lang="ts">
  import { cn } from "$lib/utils/cn";
  import type { Snippet } from "svelte";

  interface Props { children?: Snippet; class?: string; }
  let { children, class: className }: Props = $props();
</script>

<div class={cn("flex items-center p-6 pt-0", className)}>
  {#if children}{@render children()}{/if}
</div>
