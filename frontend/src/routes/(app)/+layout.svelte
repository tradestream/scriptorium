<script lang="ts">
  let { children } = $props();
</script>

<div class="flex-1 overflow-auto">
  {@render children?.()}
</div>
