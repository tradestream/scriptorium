<script lang="ts">
  import { cn } from "$lib/utils/cn";
  import type { Snippet } from "svelte";

  interface Props {
    /** ``horizontal``, ``vertical``, or ``both`` — controls overflow axes. */
    orientation?: "horizontal" | "vertical" | "both";
    /** Extra classes appended to the wrapper. */
    class?: string;
    children?: Snippet;
  }

  let {
    orientation = "vertical",
    class: className,
    children,
  }: Props = $props();

  const overflowClass =
    orientation === "horizontal"
      ? "overflow-x-auto overflow-y-hidden"
      : orientation === "both"
        ? "overflow-auto"
        : "overflow-y-auto overflow-x-hidden";
</script>

<div class={cn("relative", overflowClass, className)}>
  {@render children?.()}
</div>
