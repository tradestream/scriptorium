<script lang="ts">
  import { Button } from '$lib/components/ui/button';
  import { Separator } from '$lib/components/ui/separator';
  import { ArrowLeft, Star, Archive, ExternalLink, Highlighter } from 'lucide-svelte';
  import * as api from '$lib/api/client';
  import type { ArticleDetail } from '$lib/api/client';
  import { sanitizeMarkdown } from '$lib/utils/sanitizeHtml';

  let { data } = $props();
  let article = $state(data.article as ArticleDetail);
</script>

<div class="mx-auto max-w-3xl px-4 py-8 sm:px-6">
  <!-- Back -->
  <a href="/articles" class="mb-6 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors">
    <ArrowLeft class="h-3.5 w-3.5" /> Articles
  </a>

  <!-- Header -->
  <div class="mb-6">
    <h1 class="text-2xl font-bold tracking-tight">{article.title}</h1>
    <div class="mt-2 flex items-center gap-3 text-sm text-muted-foreground">
      {#if article.author}
        <span>{article.author}</span>
      {/if}
      {#if article.domain}
        <a href={article.url} target="_blank" rel="noopener noreferrer"
           class="flex items-center gap-1 hover:text-primary transition-colors">
          {article.domain} <ExternalLink class="h-3 w-3" />
        </a>
      {/if}
      {#if article.progress > 0}
        <span>{Math.round(article.progress * 100)}% read</span>
      {/if}
    </div>
    <div class="mt-3 flex items-center gap-2">
      <Button
        variant="outline"
        size="sm"
        onclick={async () => {
          const r = await api.starArticle(article.id);
          article.is_starred = r.starred;
        }}
      >
        <Star class="mr-1.5 h-3.5 w-3.5" fill={article.is_starred ? 'currentColor' : 'none'} />
        {article.is_starred ? 'Starred' : 'Star'}
      </Button>
      <Button
        variant="outline"
        size="sm"
        onclick={async () => {
          const r = await api.archiveArticle(article.id);
          article.is_archived = r.archived;
        }}
      >
        <Archive class="mr-1.5 h-3.5 w-3.5" />
        {article.is_archived ? 'Unarchive' : 'Archive'}
      </Button>
    </div>
  </div>

  <!-- Highlights -->
  {#if article.highlights?.length}
    <div class="mb-6 space-y-2">
      <h2 class="flex items-center gap-2 text-sm font-semibold">
        <Highlighter class="h-4 w-4 text-amber-500" />
        {article.highlights.length} Highlight{article.highlights.length === 1 ? '' : 's'}
      </h2>
      <div class="space-y-2">
        {#each article.highlights as hl}
          <div class="rounded-md border-l-4 border-amber-300 bg-amber-50/50 px-4 py-2.5 dark:border-amber-600 dark:bg-amber-950/20">
            <p class="text-sm italic text-foreground/80">"{hl.text}"</p>
            {#if hl.note}
              <p class="mt-1 text-xs text-muted-foreground">{hl.note}</p>
            {/if}
          </div>
        {/each}
      </div>
    </div>
  {/if}

  <!-- Article content -->
  {#if article.markdown_content}
    <Separator class="my-6" />
    <article class="prose prose-sm dark:prose-invert max-w-none">
      <!-- Article content comes from Instapaper / external HTML sources;
           sanitize before {@html} render to block stored XSS. -->
      {@html sanitizeMarkdown(article.markdown_content)}
    </article>
  {:else}
    <div class="mt-8 text-center text-sm text-muted-foreground">
      <p>Article content not yet cached.</p>
      <a href={article.url} target="_blank" rel="noopener noreferrer"
         class="mt-2 inline-flex items-center gap-1 text-primary hover:underline">
        Read on {article.domain} <ExternalLink class="h-3 w-3" />
      </a>
    </div>
  {/if}
</div>
