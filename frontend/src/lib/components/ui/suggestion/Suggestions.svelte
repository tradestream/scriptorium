<script lang="ts">
  import { ScrollArea } from '$lib/components/ui/scroll-area';
  import { cn } from '$lib/utils/cn';
  import type { Snippet } from 'svelte';

  interface Props {
    children?: Snippet;
    class?: string;
    orientation?: 'horizontal' | 'vertical' | 'both';
  }

  let {
    children,
    class: className,
    orientation = 'horizontal',
  }: Props = $props();
</script>

<ScrollArea {orientation} class="w-full whitespace-nowrap">
  <div class={cn('flex w-max flex-nowrap items-center gap-2', className)}>
    {@render children?.()}
  </div>
</ScrollArea>
