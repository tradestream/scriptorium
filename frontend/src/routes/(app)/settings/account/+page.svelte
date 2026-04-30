<script lang="ts">
  import { Button } from "$lib/components/ui/button";
  import { Input } from "$lib/components/ui/input";
  import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "$lib/components/ui/card";
  import { Badge } from "$lib/components/ui/badge";
  import { Separator } from "$lib/components/ui/separator";
  import { Trash2, Copy, Key } from "lucide-svelte";
  import * as api from "$lib/api/client";
  import type { ApiKey, ApiKeyCreated } from "$lib/types/index";
  import type { LayoutData } from '../$types';

  let { data }: { data: LayoutData } = $props();
  let user = $derived(data.user);

  // Profile editing
  let profileDisplayName = $state(data.user?.display_name ?? '');
  let savingProfile = $state(false);
  let profileMsg = $state('');

  async function saveProfile() {
    savingProfile = true;
    profileMsg = '';
    try {
      await api.updateProfile({ display_name: profileDisplayName.trim() });
      profileMsg = 'Saved';
      setTimeout(() => profileMsg = '', 2000);
    } catch { /* ignore */ }
    savingProfile = false;
  }

  // API Keys
  let apiKeys = $state<ApiKey[]>([]);
  let newKeyName = $state('');
  let creatingKey = $state(false);
  let newlyCreatedKey = $state<ApiKeyCreated | null>(null);
  let showNewKey = $state(false);

  async function loadApiKeys() {
    try { apiKeys = await api.getApiKeys(); } catch { /* non-critical */ }
  }

  $effect(() => { loadApiKeys(); });

  async function createApiKey() {
    if (!newKeyName.trim()) return;
    creatingKey = true;
    try {
      const created = await api.createApiKey(newKeyName.trim());
      newlyCreatedKey = created;
      showNewKey = true;
      newKeyName = '';
      await loadApiKeys();
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Failed to create key');
    } finally { creatingKey = false; }
  }

  async function revokeApiKey(id: number) {
    if (!confirm('Revoke this API key?')) return;
    try { await api.revokeApiKey(id); await loadApiKeys(); }
    catch (e) { alert(e instanceof Error ? e.message : 'Failed'); }
  }

  async function copyKey() {
    if (!newlyCreatedKey) return;
    await navigator.clipboard.writeText(newlyCreatedKey.key);
  }

  // Devices
  let devices = $state<import('$lib/api/client').Device[]>([]);
  async function loadDevices() {
    try { devices = await api.getDevices(); } catch { /* non-critical */ }
  }
  $effect(() => { loadDevices(); });

  async function removeDevice(id: number) {
    await api.deleteDevice(id);
    devices = devices.filter(d => d.id !== id);
  }
</script>

<!-- Account -->
<Card>
  <CardHeader>
    <CardTitle>Account</CardTitle>
    <CardDescription>Your account details</CardDescription>
  </CardHeader>
  <CardContent class="space-y-4">
    <div class="space-y-2">
      <label for="username" class="text-sm font-medium">Username</label>
      <Input id="username" value={user?.username ?? ''} disabled />
    </div>
    <div class="space-y-2">
      <label for="display-name" class="text-sm font-medium">Display Name</label>
      <div class="flex gap-2">
        <Input id="display-name" bind:value={profileDisplayName} placeholder="Your full name" />
        <Button
          variant="outline"
          size="sm"
          onclick={saveProfile}
          disabled={savingProfile}
          class="shrink-0"
        >
          {savingProfile ? 'Saving…' : 'Save'}
        </Button>
      </div>
      {#if profileMsg}
        <p class="text-xs text-green-600 dark:text-green-400">{profileMsg}</p>
      {/if}
    </div>
    <div class="space-y-2">
      <label for="email" class="text-sm font-medium">Email</label>
      <Input id="email" type="email" value={user?.email ?? ''} disabled />
    </div>
    {#if user?.is_admin}
      <Badge variant="outline">Administrator</Badge>
    {/if}
  </CardContent>
</Card>

<!-- API Keys -->
<Card>
  <CardHeader>
    <CardTitle>API Keys</CardTitle>
    <CardDescription>Use API keys to access Scriptorium from scripts or external apps without your password</CardDescription>
  </CardHeader>
  <CardContent class="space-y-4">
    {#if newlyCreatedKey && showNewKey}
      <div class="rounded-md border border-amber-300 bg-amber-50 p-3 dark:border-amber-700 dark:bg-amber-950/30">
        <p class="mb-1.5 text-sm font-medium text-amber-800 dark:text-amber-200">Copy your key now — it won't be shown again</p>
        <div class="flex items-center gap-2">
          <code class="flex-1 truncate rounded bg-background px-2 py-1 font-mono text-xs">{newlyCreatedKey.key}</code>
          <Button size="sm" variant="outline" onclick={copyKey}><Copy class="mr-1.5 h-3.5 w-3.5" />Copy</Button>
          <Button size="sm" variant="ghost" onclick={() => { showNewKey = false; newlyCreatedKey = null; }}>Dismiss</Button>
        </div>
      </div>
    {/if}

    {#if apiKeys.length > 0}
      <div class="space-y-2">
        {#each apiKeys as key}
          <div class="flex items-center justify-between rounded-md border p-3">
            <div>
              <p class="text-sm font-medium">{key.name}</p>
              <p class="font-mono text-xs text-muted-foreground">{key.prefix}…</p>
              <p class="text-xs text-muted-foreground">
                Created {new Date(key.created_at).toLocaleDateString()}
                {#if key.last_used_at} · Last used {new Date(key.last_used_at).toLocaleDateString()}{/if}
              </p>
            </div>
            <Button variant="ghost" size="icon" onclick={() => revokeApiKey(key.id)} title="Revoke" class="text-destructive hover:text-destructive">
              <Trash2 class="h-4 w-4" />
            </Button>
          </div>
        {/each}
      </div>
      <Separator />
    {/if}

    <div class="flex gap-2">
      <Input
        placeholder="Key name (e.g. Home Script)"
        bind:value={newKeyName}
        class="flex-1"
        onkeydown={(e) => { if (e.key === 'Enter') createApiKey(); }}
      />
      <Button size="sm" onclick={createApiKey} disabled={creatingKey || !newKeyName.trim()}>
        <Key class="mr-1.5 h-3.5 w-3.5" />{creatingKey ? 'Creating…' : 'Generate'}
      </Button>
    </div>
  </CardContent>
</Card>

<!-- Connected Devices -->
<Card>
  <CardHeader>
    <CardTitle>Connected Devices</CardTitle>
    <CardDescription>E-readers and apps syncing with your account</CardDescription>
  </CardHeader>
  <CardContent class="space-y-2">
    {#if devices.length === 0}
      <p class="text-sm text-muted-foreground">No devices connected yet.</p>
    {:else}
      {#each devices as device}
        <div class="flex items-center justify-between rounded-md border p-3">
          <div>
            <p class="text-sm font-medium">{device.name}</p>
            <p class="text-xs text-muted-foreground capitalize">{device.device_type}{#if device.device_model} · {device.device_model}{/if}</p>
            {#if device.last_synced}
              <p class="text-xs text-muted-foreground">Last synced {new Date(device.last_synced).toLocaleDateString()}</p>
            {/if}
          </div>
          <Button variant="ghost" size="icon" onclick={() => removeDevice(device.id)} title="Remove device" class="text-destructive hover:text-destructive">
            <Trash2 class="h-4 w-4" />
          </Button>
        </div>
      {/each}
    {/if}
  </CardContent>
</Card>
