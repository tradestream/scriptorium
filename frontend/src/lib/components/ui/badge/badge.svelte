<script lang="ts">
  import { cn } from "$lib/utils/cn";
  import type { BadgeVariant } from "./index";
  import type { Snippet } from "svelte";

  interface Props {
    variant?: BadgeVariant;
    children?: Snippet;
    class?: string;
  }

  let { variant = "default", children, class: className }: Props = $props();

  const variants: Record<BadgeVariant, string> = {
    default: "border-transparent bg-primary text-primary-foreground shadow",
    secondary: "border-transparent bg-secondary text-secondary-foreground",
    destructive: "border-transparent bg-destructive text-destructive-foreground shadow",
    outline: "text-foreground",
  };
</script>

<span
  class={cn(
    "inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
    variants[variant],
    className
  )}
>
  {#if children}
    {@render children()}
  {/if}
</span>
