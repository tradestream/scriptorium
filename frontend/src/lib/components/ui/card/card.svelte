<script lang="ts">
  import { cn } from "$lib/utils/cn";
  import type { Snippet } from "svelte";
  import type { HTMLAttributes } from "svelte/elements";

  interface Props extends HTMLAttributes<HTMLDivElement> {
    children?: Snippet;
    class?: string;
  }

  let { children, class: className, ...restProps }: Props = $props();
</script>

<div class={cn("rounded-xl border bg-card text-card-foreground shadow", className)} {...restProps}>
  {#if children}
    {@render children()}
  {/if}
</div>
