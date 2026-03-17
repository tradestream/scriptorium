<script lang="ts">
  import { onMount } from 'svelte';
  import { Button } from '$lib/components/ui/button';
  import { Input } from '$lib/components/ui/input';
  import { Newspaper, Plus, Star, Archive, RefreshCw, Trash2, ExternalLink, Link2, Unlink } from 'lucide-svelte';
  import * as api from '$lib/api/client';
  import type { ArticleItem } from '$lib/api/client';

  let articles = $state<ArticleItem[]>([]);
  let loading = $state(true);
  let tab = $state<'unread' | 'starred' | 'archived'>('unread');
  let instapaperLinked = $state(false);
  let instapaperUser = $state('');
  let hasFullApi = $state(false);

  // Save form
  let showSaveForm = $state(false);
  let saveUrl = $state('');
  let saving = $state(false);

  // Instapaper linking
  let showLinkForm = $state(false);
  let ipUser = $state('');
  let ipPass = $state('');
  let linking = $state(false);
  let linkMsg = $state('');

  // Sync
  let syncing = $state(false);
  let syncMsg = $state('');

  async function loadArticles() {
    loading = true;
    try {
      articles = await api.getArticles({
        archived: tab === 'archived',
        starred: tab === 'starred' ? true : undefined,
      });
    } catch { /* ignore */ }
    loading = false;
  }

  async function checkInstapaper() {
    try {
      const s = await api.getInstapaperStatus();
      instapaperLinked = s.linked;
      instapaperUser = s.instapaper_username ?? '';
      hasFullApi = s.has_full_api;
    } catch { /* ignore */ }
  }

  onMount(() => {
    checkInstapaper();
    loadArticles();
  });

  async function handleSave() {
    if (!saveUrl.trim()) return;
    saving = true;
    try {
      await api.saveArticle(saveUrl.trim());
      saveUrl = '';
      showSaveForm = false;
      await loadArticles();
    } catch { /* ignore */ }
    saving = false;
  }

  async function handleStar(id: number) {
    const result = await api.starArticle(id);
    const idx = articles.findIndex(a => a.id === id);
    if (idx >= 0) articles[idx].is_starred = result.starred;
  }

  async function handleArchive(id: number) {
    await api.archiveArticle(id);
    await loadArticles();
  }

  async function handleDelete(id: number) {
    await api.deleteArticle(id);
    articles = articles.filter(a => a.id !== id);
  }

  async function handleSync() {
    syncing = true;
    syncMsg = '';
    try {
      const r = await api.syncInstapaper();
      syncMsg = `Synced: ${r.created} new, ${r.updated} updated, ${r.highlights} highlights`;
      await loadArticles();
    } catch (e) {
      syncMsg = e instanceof Error ? e.message : 'Sync failed';
    }
    syncing = false;
  }

  async function handleLink() {
    linking = true;
    linkMsg = '';
    try {
      await api.linkInstapaper(ipUser, ipPass);
      instapaperLinked = true;
      showLinkForm = false;
      ipPass = '';
      linkMsg = 'Linked!';
    } catch (e) {
      linkMsg = e instanceof Error ? e.message : 'Failed';
    }
    linking = false;
  }

  async function handleUnlink() {
    await api.unlinkInstapaper();
    instapaperLinked = false;
  }

  function switchTab(t: 'unread' | 'starred' | 'archived') {
    tab = t;
    loadArticles();
  }
</script>

<div class="mx-auto max-w-4xl px-4 py-8 sm:px-6">
  <!-- Header -->
  <div class="flex items-center justify-between mb-6">
    <div class="flex items-center gap-3">
      <Newspaper class="h-6 w-6 text-muted-foreground/50" />
      <h1 class="text-2xl font-bold tracking-tight">Articles</h1>
    </div>
    <div class="flex items-center gap-2">
      {#if instapaperLinked}
        <span class="text-xs text-muted-foreground">{instapaperUser}</span>
        {#if hasFullApi}
          <Button variant="outline" size="sm" onclick={handleSync} disabled={syncing}>
            <RefreshCw class="mr-1.5 h-3.5 w-3.5 {syncing ? 'animate-spin' : ''}" />
            {syncing ? 'Syncing…' : 'Sync'}
          </Button>
        {/if}
        <Button variant="ghost" size="sm" onclick={handleUnlink} title="Unlink Instapaper">
          <Unlink class="h-3.5 w-3.5" />
        </Button>
      {:else}
        <Button variant="outline" size="sm" onclick={() => showLinkForm = !showLinkForm}>
          <Link2 class="mr-1.5 h-3.5 w-3.5" />
          Link Instapaper
        </Button>
      {/if}
      <Button size="sm" onclick={() => showSaveForm = !showSaveForm}>
        <Plus class="mr-1.5 h-3.5 w-3.5" />
        Save Article
      </Button>
    </div>
  </div>

  {#if syncMsg}
    <p class="mb-4 text-sm text-muted-foreground">{syncMsg}</p>
  {/if}

  <!-- Instapaper link form -->
  {#if showLinkForm && !instapaperLinked}
    <div class="mb-6 rounded-lg border p-4 space-y-3">
      <p class="text-sm font-medium">Link your Instapaper account</p>
      <p class="text-xs text-muted-foreground">Articles you save will sync to your Kobo via Instapaper.</p>
      <div class="grid grid-cols-2 gap-3">
        <Input bind:value={ipUser} placeholder="Instapaper email" />
        <Input bind:value={ipPass} type="password" placeholder="Password" onkeydown={(e) => { if (e.key === 'Enter') handleLink(); }} />
      </div>
      {#if linkMsg}
        <p class="text-xs text-destructive">{linkMsg}</p>
      {/if}
      <Button size="sm" onclick={handleLink} disabled={linking || !ipUser || !ipPass}>
        {linking ? 'Linking…' : 'Connect'}
      </Button>
    </div>
  {/if}

  <!-- Save article form -->
  {#if showSaveForm}
    <div class="mb-6 flex gap-2">
      <Input
        bind:value={saveUrl}
        placeholder="Paste article URL…"
        class="flex-1"
        onkeydown={(e) => { if (e.key === 'Enter') handleSave(); }}
      />
      <Button onclick={handleSave} disabled={saving || !saveUrl.trim()}>
        {saving ? 'Saving…' : 'Save'}
      </Button>
    </div>
  {/if}

  <!-- Tabs -->
  <div class="flex items-center gap-1 rounded-md border bg-background px-1.5 py-1 mb-6 w-fit">
    <button
      onclick={() => switchTab('unread')}
      class="rounded px-3 py-1 text-sm transition-colors {tab === 'unread' ? 'bg-foreground/10 text-foreground font-medium' : 'text-muted-foreground hover:text-foreground'}"
    >Unread</button>
    <button
      onclick={() => switchTab('starred')}
      class="rounded px-3 py-1 text-sm transition-colors {tab === 'starred' ? 'bg-foreground/10 text-foreground font-medium' : 'text-muted-foreground hover:text-foreground'}"
    >Starred</button>
    <button
      onclick={() => switchTab('archived')}
      class="rounded px-3 py-1 text-sm transition-colors {tab === 'archived' ? 'bg-foreground/10 text-foreground font-medium' : 'text-muted-foreground hover:text-foreground'}"
    >Archive</button>
  </div>

  <!-- Article list -->
  {#if loading}
    <div class="space-y-3">
      {#each Array(5) as _}
        <div class="h-20 animate-pulse rounded-lg bg-muted"></div>
      {/each}
    </div>
  {:else if articles.length === 0}
    <div class="flex flex-col items-center gap-4 py-20 text-center">
      <Newspaper class="h-12 w-12 text-muted-foreground/30" />
      <p class="text-muted-foreground">
        {tab === 'unread' ? 'No articles yet. Save a URL to get started.' : `No ${tab} articles.`}
      </p>
    </div>
  {:else}
    <div class="divide-y rounded-lg border bg-card overflow-hidden">
      {#each articles as article}
        <div class="flex items-start gap-4 px-4 py-3 hover:bg-muted/30 transition-colors">
          <div class="flex-1 min-w-0">
            <a href="/articles/{article.id}" class="font-medium text-sm hover:text-primary transition-colors line-clamp-1">
              {article.title}
            </a>
            <div class="flex items-center gap-2 mt-0.5 text-xs text-muted-foreground">
              {#if article.domain}
                <span>{article.domain}</span>
              {/if}
              {#if article.author}
                <span>· {article.author}</span>
              {/if}
              {#if article.progress > 0}
                <span>· {Math.round(article.progress * 100)}% read</span>
              {/if}
              {#if article.highlight_count}
                <span>· {article.highlight_count} highlights</span>
              {/if}
            </div>
          </div>
          <div class="flex items-center gap-1 shrink-0">
            <button
              onclick={() => handleStar(article.id)}
              class="rounded p-1 transition-colors {article.is_starred ? 'text-amber-400' : 'text-muted-foreground/30 hover:text-amber-400'}"
              title={article.is_starred ? 'Unstar' : 'Star'}
            >
              <Star class="h-4 w-4" fill={article.is_starred ? 'currentColor' : 'none'} />
            </button>
            <button
              onclick={() => handleArchive(article.id)}
              class="rounded p-1 text-muted-foreground/30 hover:text-foreground transition-colors"
              title={article.is_archived ? 'Unarchive' : 'Archive'}
            >
              <Archive class="h-4 w-4" />
            </button>
            <a href={article.url} target="_blank" rel="noopener noreferrer"
               class="rounded p-1 text-muted-foreground/30 hover:text-foreground transition-colors"
               title="Open original">
              <ExternalLink class="h-4 w-4" />
            </a>
            <button
              onclick={() => handleDelete(article.id)}
              class="rounded p-1 text-muted-foreground/30 hover:text-destructive transition-colors"
              title="Delete"
            >
              <Trash2 class="h-4 w-4" />
            </button>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
