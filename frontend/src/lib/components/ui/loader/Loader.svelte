<script lang="ts">
  import LoaderIcon from './LoaderIcon.svelte';
  import { cn } from '$lib/utils/cn';

  let { size = 16, class: className, ...rest }: { size?: number; class?: string } = $props();
</script>

<div class={cn('inline-flex animate-spin items-center justify-center', className)} {...rest}>
  <LoaderIcon {size} />
</div>
