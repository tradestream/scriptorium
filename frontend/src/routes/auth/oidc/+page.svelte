<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { setAuthToken } from '$lib/api/client';
  import { onMount } from 'svelte';

  onMount(() => {
    const token = $page.url.searchParams.get('token');
    if (token) {
      setAuthToken(token);
      goto('/');
    } else {
      goto('/auth/login?error=oidc_failed');
    }
  });
</script>

<div class="flex min-h-screen items-center justify-center">
  <p class="text-muted-foreground">Completing sign in...</p>
</div>
