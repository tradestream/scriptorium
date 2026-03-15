<script lang="ts">
  import { Button } from '$lib/components/ui/button';
  import { UseClipboard } from '$lib/hooks/use-clipboard.svelte';
  import { cn } from '$lib/utils/cn';
  import { Check, Copy, X } from 'lucide-svelte';
  import { scale } from 'svelte/transition';
  import type { Snippet } from 'svelte';

  interface Props {
    text: string;
    icon?: Snippet;
    animationDuration?: number;
    variant?: 'ghost' | 'outline' | 'default' | 'secondary' | 'destructive' | 'link';
    size?: 'default' | 'sm' | 'lg' | 'icon';
    onCopy?: (status: 'success' | 'failure' | undefined) => void;
    class?: string;
    tabindex?: number;
    children?: Snippet;
  }

  let {
    text,
    icon,
    animationDuration = 500,
    variant = 'ghost',
    size = 'icon',
    onCopy,
    class: className,
    tabindex = -1,
    children,
  }: Props = $props();

  if (size === 'icon' && children) size = 'default';

  const clipboard = new UseClipboard();
</script>

<Button
  {variant}
  {size}
  {tabindex}
  class={cn('flex items-center gap-2', className)}
  type="button"
  onclick={async () => {
    const status = await clipboard.copy(text);
    onCopy?.(status);
  }}
>
  {#if clipboard.status === 'success'}
    <div in:scale={{ duration: animationDuration, start: 0.85 }}>
      <Check class="h-4 w-4" stroke-width={1.8} />
      <span class="sr-only">Copied</span>
    </div>
  {:else if clipboard.status === 'failure'}
    <div in:scale={{ duration: animationDuration, start: 0.85 }}>
      <X class="h-4 w-4" stroke-width={1.8} />
      <span class="sr-only">Failed to copy</span>
    </div>
  {:else}
    <div in:scale={{ duration: animationDuration, start: 0.85 }}>
      {#if icon}
        {@render icon()}
      {:else}
        <Copy class="h-4 w-4" stroke-width={1.8} />
      {/if}
      <span class="sr-only">Copy</span>
    </div>
  {/if}
  {@render children?.()}
</Button>
