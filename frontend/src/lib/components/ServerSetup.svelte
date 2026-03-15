<script lang="ts">
  import { setServerUrl } from '$lib/api/client';
  import { BookOpen, Wifi, AlertCircle, CheckCircle, ArrowRight } from 'lucide-svelte';

  interface Props {
    onComplete: () => void;
  }

  let { onComplete }: Props = $props();

  let serverUrl = $state('');
  let testing = $state(false);
  let testResult = $state<'ok' | 'error' | null>(null);
  let testError = $state('');

  async function testConnection() {
    const url = serverUrl.trim().replace(/\/+$/, '');
    if (!url) return;
    testing = true;
    testResult = null;
    testError = '';
    try {
      const r = await fetch(`${url}/api/v1/auth/me`, { signal: AbortSignal.timeout(6000) });
      // 401 is fine — it means the server is reachable, just not authenticated yet
      if (r.status === 401 || r.ok) {
        testResult = 'ok';
      } else {
        testResult = 'error';
        testError = `Server responded with ${r.status}`;
      }
    } catch (e) {
      testResult = 'error';
      testError = e instanceof Error ? e.message : 'Cannot reach server';
    } finally {
      testing = false;
    }
  }

  async function connect() {
    const url = serverUrl.trim().replace(/\/+$/, '');
    if (!url) return;
    setServerUrl(url);
    onComplete();
  }
</script>

<div class="fixed inset-0 z-50 flex flex-col items-center justify-center bg-background px-6 pb-safe">
  <div class="w-full max-w-sm space-y-8">

    <!-- Logo / wordmark -->
    <div class="flex flex-col items-center gap-3 text-center">
      <div class="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10">
        <BookOpen class="h-8 w-8 text-primary" />
      </div>
      <div>
        <h1 class="text-2xl font-bold tracking-tight">Scriptorium</h1>
        <p class="mt-1 text-sm text-muted-foreground">Enter your server address to get started</p>
      </div>
    </div>

    <!-- Server URL input -->
    <div class="space-y-3">
      <div class="space-y-1.5">
        <label for="server-url" class="text-sm font-medium">Server URL</label>
        <div class="relative">
          <Wifi class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            id="server-url"
            type="url"
            inputmode="url"
            autocomplete="off"
            autocorrect="off"
            autocapitalize="none"
            spellcheck={false}
            placeholder="http://192.168.1.10:8000"
            bind:value={serverUrl}
            onkeydown={(e) => { if (e.key === 'Enter') testConnection(); }}
            class="w-full rounded-lg border bg-background py-3 pl-9 pr-4 text-sm outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <p class="text-xs text-muted-foreground">Your Scriptorium server on the local network</p>
      </div>

      <!-- Test result -->
      {#if testResult === 'ok'}
        <div class="flex items-center gap-2 rounded-md bg-green-50 px-3 py-2 text-sm text-green-700 dark:bg-green-950/30 dark:text-green-400">
          <CheckCircle class="h-4 w-4 shrink-0" />
          Server reachable
        </div>
      {:else if testResult === 'error'}
        <div class="flex items-start gap-2 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          <AlertCircle class="mt-0.5 h-4 w-4 shrink-0" />
          <span>{testError || 'Cannot reach server — check the URL and your network'}</span>
        </div>
      {/if}

      <!-- Buttons -->
      <div class="flex gap-2">
        <button
          onclick={testConnection}
          disabled={testing || !serverUrl.trim()}
          class="flex-1 rounded-lg border py-3 text-sm font-medium transition-colors disabled:opacity-50 hover:bg-muted"
        >
          {testing ? 'Testing…' : 'Test Connection'}
        </button>
        <button
          onclick={connect}
          disabled={!serverUrl.trim()}
          class="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-primary py-3 text-sm font-medium text-primary-foreground transition-opacity disabled:opacity-50"
        >
          Connect <ArrowRight class="h-4 w-4" />
        </button>
      </div>
    </div>

    <!-- Help text -->
    <p class="text-center text-xs text-muted-foreground">
      Find your server address in Scriptorium Settings → System Configuration
    </p>

  </div>
</div>
