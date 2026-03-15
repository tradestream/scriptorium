<script lang="ts">
  let { children } = $props();
</script>

<!-- Full-screen reader layout — no sidebar or header -->
<div class="h-screen w-screen overflow-hidden bg-background">
  {@render children()}
</div>
