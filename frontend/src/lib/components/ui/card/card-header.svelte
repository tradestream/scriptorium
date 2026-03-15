<script lang="ts">
  import { cn } from "$lib/utils/cn";
  import type { Snippet } from "svelte";

  interface Props { children?: Snippet; class?: string; }
  let { children, class: className }: Props = $props();
</script>

<div class={cn("flex flex-col space-y-1.5 p-6", className)}>
  {#if children}{@render children()}{/if}
</div>
