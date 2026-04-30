<script lang="ts">
  import { Button } from "$lib/components/ui/button";
  import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "$lib/components/ui/card";
  import { Badge } from "$lib/components/ui/badge";
  import { Separator } from "$lib/components/ui/separator";
  import { RefreshCw, CheckCircle, AlertCircle, Download } from "lucide-svelte";
  import * as api from "$lib/api/client";
  import type { LayoutData } from '../$types';

  let { data }: { data: LayoutData } = $props();
  let user = $derived(data.user);
  let adminConfig = $derived(data.adminConfig);

  let rebuildingIndex = $state(false);
  let rebuildIndexMsg = $state('');

  async function rebuildSearchIndex() {
    rebuildingIndex = true;
    rebuildIndexMsg = '';
    try {
      const result = await api.rebuildSearchIndex();
      rebuildIndexMsg = `Done — ${result.indexed} works indexed.`;
    } catch (e: any) {
      rebuildIndexMsg = e?.message ?? 'Failed to rebuild index.';
    } finally {
      rebuildingIndex = false;
    }
  }
</script>

<!-- System Config (admin) -->
{#if user?.is_admin && adminConfig}
  <Card>
    <CardHeader>
      <CardTitle>System Configuration</CardTitle>
      <CardDescription>
        Current server settings — edit the <code class="rounded bg-muted px-1 py-0.5 text-xs">.env</code> file to change these
      </CardDescription>
    </CardHeader>
    <CardContent class="space-y-4">
      <!-- Paths -->
      <div class="grid grid-cols-2 gap-3 text-sm">
        <div>
          <p class="font-medium text-muted-foreground">Library Path</p>
          <code class="text-xs">{adminConfig.library_path}</code>
        </div>
        <div>
          <p class="font-medium text-muted-foreground">Ingest Path</p>
          <code class="text-xs">{adminConfig.ingest_path}</code>
        </div>
        <div>
          <p class="font-medium text-muted-foreground">Calibre Path</p>
          <code class="text-xs">{adminConfig.calibre_path}</code>
        </div>
        <div>
          <p class="font-medium text-muted-foreground">LLM Provider</p>
          <span class="flex items-center gap-1 text-xs">
            {adminConfig.llm_provider}
            {#if adminConfig.llm_configured}
              <CheckCircle class="h-3 w-3 text-green-500" />
            {:else}
              <AlertCircle class="h-3 w-3 text-amber-500" />
            {/if}
          </span>
        </div>
      </div>

      <Separator />

      <!-- Ingest preferences -->
      <div>
        <p class="text-sm font-medium">Auto-Ingest Preferences</p>
        <div class="mt-2 grid grid-cols-2 gap-3 text-sm">
          <div>
            <p class="text-xs text-muted-foreground">Auto-Convert</p>
            <p>{adminConfig.ingest_auto_convert ? `Yes → ${adminConfig.ingest_target_format.toUpperCase()}` : 'Disabled'}</p>
          </div>
          <div>
            <p class="text-xs text-muted-foreground">Auto-Enrich</p>
            <p>{adminConfig.ingest_auto_enrich ? `Yes${adminConfig.ingest_default_provider ? ` (${adminConfig.ingest_default_provider})` : ''}` : 'Disabled'}</p>
          </div>
        </div>
        <p class="mt-2 text-xs text-muted-foreground">
          Set <code class="rounded bg-muted px-1">INGEST_AUTO_CONVERT</code>,
          <code class="rounded bg-muted px-1">INGEST_TARGET_FORMAT</code>,
          <code class="rounded bg-muted px-1">INGEST_AUTO_ENRICH</code> in your <code class="rounded bg-muted px-1">.env</code> file.
        </p>
      </div>

      <Separator />

      <!-- OIDC -->
      <div>
        <div class="flex items-center gap-2">
          <p class="text-sm font-medium">Single Sign-On (OIDC)</p>
          {#if adminConfig.oidc_configured}
            <Badge variant="secondary" class="text-xs">Enabled</Badge>
          {:else}
            <Badge variant="outline" class="text-xs text-muted-foreground">Disabled</Badge>
          {/if}
        </div>
        {#if adminConfig.oidc_configured}
          <p class="mt-1 text-xs text-muted-foreground">
            Provider: <code class="rounded bg-muted px-1">{adminConfig.oidc_discovery_url}</code>
          </p>
        {:else}
          <p class="mt-1 text-xs text-muted-foreground">
            Set <code class="rounded bg-muted px-1">OIDC_ENABLED=true</code>,
            <code class="rounded bg-muted px-1">OIDC_DISCOVERY_URL</code>,
            <code class="rounded bg-muted px-1">OIDC_CLIENT_ID</code>, and
            <code class="rounded bg-muted px-1">OIDC_CLIENT_SECRET</code> to enable SSO.
          </p>
        {/if}
      </div>

      <Separator />

      <!-- SMTP -->
      <div>
        <div class="flex items-center gap-2">
          <p class="text-sm font-medium">Email / Send-to-Device (SMTP)</p>
          {#if adminConfig.smtp_configured}
            <Badge variant="secondary" class="text-xs">Configured</Badge>
          {:else}
            <Badge variant="outline" class="text-xs text-muted-foreground">Not configured</Badge>
          {/if}
        </div>
        {#if adminConfig.smtp_configured}
          <div class="mt-2 grid grid-cols-2 gap-3 text-sm">
            <div>
              <p class="text-xs text-muted-foreground">Host</p>
              <p>{adminConfig.smtp_host}:{adminConfig.smtp_port}</p>
            </div>
            <div>
              <p class="text-xs text-muted-foreground">From</p>
              <p>{adminConfig.smtp_from ?? adminConfig.smtp_user}</p>
            </div>
          </div>
        {:else}
          <p class="mt-1 text-xs text-muted-foreground">
            Set <code class="rounded bg-muted px-1">SMTP_HOST</code>, <code class="rounded bg-muted px-1">SMTP_USER</code>,
            <code class="rounded bg-muted px-1">SMTP_PASS</code>, and <code class="rounded bg-muted px-1">SMTP_FROM</code> to enable email delivery.
          </p>
        {/if}
      </div>
    </CardContent>
  </Card>

  <!-- Search Index -->
  <Card>
    <CardHeader>
      <CardTitle>Search Index</CardTitle>
      <CardDescription>Rebuild the full-text search index from scratch</CardDescription>
    </CardHeader>
    <CardContent>
      <p class="text-sm text-muted-foreground">
        Run this if search returns no results or seems stale. Reindexes all works in the database.
      </p>
      <div class="mt-4 flex items-center gap-3">
        <Button variant="outline" onclick={rebuildSearchIndex} disabled={rebuildingIndex}>
          <RefreshCw class="mr-2 h-4 w-4 {rebuildingIndex ? 'animate-spin' : ''}" />
          {rebuildingIndex ? 'Rebuilding…' : 'Rebuild Index'}
        </Button>
        {#if rebuildIndexMsg}
          <span class="text-sm text-muted-foreground">{rebuildIndexMsg}</span>
        {/if}
      </div>
    </CardContent>
  </Card>

  <!-- Backup -->
  <Card>
    <CardHeader>
      <CardTitle>Backup</CardTitle>
      <CardDescription>Download a snapshot of the database and config</CardDescription>
    </CardHeader>
    <CardContent>
      <p class="text-sm text-muted-foreground">
        Creates a <code class="rounded bg-muted px-1 py-0.5 text-xs">.tar.gz</code> archive containing
        the SQLite database and any config files.
      </p>
      <Button class="mt-4" href={api.adminBackupUrl()} download>
        <Download class="mr-2 h-4 w-4" /> Download Backup
      </Button>
    </CardContent>
  </Card>
{/if}
