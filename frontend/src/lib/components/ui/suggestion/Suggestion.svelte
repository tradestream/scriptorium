<script lang="ts">
  import { Button } from '$lib/components/ui/button';
  import { cn } from '$lib/utils/cn';
  import type { Snippet } from 'svelte';

  interface Props {
    suggestion: string;
    onclick?: (suggestion: string) => void;
    class?: string;
    variant?: 'outline' | 'ghost' | 'secondary' | 'default';
    size?: 'default' | 'sm' | 'lg' | 'icon';
    children?: Snippet;
  }

  let {
    suggestion,
    onclick,
    class: className,
    variant = 'outline',
    size = 'sm',
    children,
    ...rest
  }: Props = $props();
</script>

<Button
  class={cn('rounded-full px-4 font-normal', className)}
  onclick={() => onclick?.(suggestion)}
  {size}
  type="button"
  {variant}
  {...rest}
>
  {#if children}
    {@render children()}
  {:else}
    {suggestion}
  {/if}
</Button>
