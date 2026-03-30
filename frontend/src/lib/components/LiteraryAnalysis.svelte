<script lang="ts">
  import { Button } from "$lib/components/ui/button";
  import { Card, CardContent, CardHeader, CardTitle } from "$lib/components/ui/card";
  import { Badge } from "$lib/components/ui/badge";
  import { Separator } from "$lib/components/ui/separator";
  import {
    BookOpen,
    ChevronDown,
    ChevronUp,
    Loader2,
    Music,
    Pen,
    Trash2,
  } from "lucide-svelte";
  import * as api from "$lib/api/client";
  import type { LiteraryAnalysis, LiteraryAnalysisRequest } from "$lib/api/client";

  interface Props {
    bookId: string;
  }

  let { bookId }: Props = $props();

  let analyses = $state<LiteraryAnalysis[]>([]);
  let running = $state(false);
  let expandedId = $state<number | null>(null);
  let showTypeSelect = $state(false);

  const analysisTypes: { value: string; label: string; icon: typeof Music; mode: 'poetry' | 'prose'; description: string }[] = [
    { value: "literary_full_poetry", label: "Full Poetry Analysis", icon: Music, mode: "poetry", description: "Prosody, sound, form, figurative language, diction, speaker (30 tools)" },
    { value: "literary_full_prose", label: "Full Prose Analysis", icon: Pen, mode: "prose", description: "Narrative structure, diction, vocabulary, intertextual, speaker (30 tools)" },
  ];

  async function loadAnalyses() {
    try {
      analyses = await api.getLiteraryAnalyses(bookId);
    } catch (e) {
      console.error("Failed to load literary analyses:", e);
    }
  }

  async function runAnalysis(type: typeof analysisTypes[number]) {
    running = true;
    try {
      const result = await api.runLiteraryAnalysis(bookId, {
        analysis_type: type.value,
        mode: type.mode,
      });
      analyses = [result, ...analyses];
      showTypeSelect = false;
      expandedId = result.id;
    } catch (e) {
      console.error("Failed to run literary analysis:", e);
    } finally {
      running = false;
    }
  }

  async function deleteAnalysis(analysisId: number) {
    try {
      await api.deleteLiteraryAnalysis(bookId, analysisId);
      analyses = analyses.filter((a) => a.id !== analysisId);
      if (expandedId === analysisId) expandedId = null;
    } catch (e) {
      console.error("Failed to delete:", e);
    }
  }

  function toggleExpand(id: number) {
    expandedId = expandedId === id ? null : id;
  }

  function getIcon(type: string) {
    return analysisTypes.find((t) => t.value === type)?.icon ?? BookOpen;
  }

  function getLabel(type: string) {
    return analysisTypes.find((t) => t.value === type)?.label ?? type;
  }

  function formatResultKey(key: string): string {
    return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }

  $effect(() => {
    loadAnalyses();
  });
</script>

<Card>
  <CardHeader class="pb-3">
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <BookOpen class="h-5 w-5 text-primary" />
        <CardTitle class="text-lg">Literary Analysis</CardTitle>
        {#if analyses.length > 0}
          <Badge variant="secondary">{analyses.length}</Badge>
        {/if}
      </div>
      <Button
        size="sm"
        disabled={running}
        onclick={() => showTypeSelect = !showTypeSelect}
      >
        {#if running}
          <Loader2 class="mr-2 h-4 w-4 animate-spin" /> Analyzing...
        {:else}
          <BookOpen class="mr-2 h-4 w-4" /> Analyze
        {/if}
      </Button>
    </div>
  </CardHeader>
  <CardContent class="space-y-3">
    {#if showTypeSelect}
      <div class="space-y-2 rounded-md border bg-muted/50 p-3">
        <p class="text-sm font-medium">Choose analysis mode:</p>
        {#each analysisTypes as type}
          {@const Icon = type.icon}
          <button
            class="flex w-full items-start gap-3 rounded-md p-2 text-left text-sm transition-colors hover:bg-accent"
            onclick={() => runAnalysis(type)}
            disabled={running}
          >
            <Icon class="mt-0.5 h-4 w-4 shrink-0 text-primary" />
            <div>
              <p class="font-medium">{type.label}</p>
              <p class="text-xs text-muted-foreground">{type.description}</p>
            </div>
          </button>
        {/each}
        <Button variant="outline" size="sm" class="w-full" onclick={() => showTypeSelect = false}>
          Cancel
        </Button>
      </div>
    {/if}

    {#if analyses.length === 0 && !running}
      <p class="py-4 text-center text-sm text-muted-foreground">
        No literary analyses yet. Run a computational analysis of prosody, form, figurative language, diction, and more.
      </p>
    {/if}

    {#each analyses as analysis (analysis.id)}
      {@const Icon = getIcon(analysis.analysis_type)}
      <div class="rounded-md border">
        <button
          class="flex w-full items-center gap-2 p-3 text-left text-sm hover:bg-muted/50"
          onclick={() => toggleExpand(analysis.id)}
        >
          <Icon class="h-4 w-4 shrink-0 text-primary" />
          <span class="flex-1 font-medium">{getLabel(analysis.analysis_type)}</span>
          <Badge variant={analysis.status === "completed" ? "secondary" : "destructive"} class="text-xs">
            {analysis.status}
          </Badge>
          <span class="text-xs text-muted-foreground">
            {new Date(analysis.created_at).toLocaleDateString()}
          </span>
          {#if expandedId === analysis.id}
            <ChevronUp class="h-4 w-4" />
          {:else}
            <ChevronDown class="h-4 w-4" />
          {/if}
        </button>

        {#if expandedId === analysis.id}
          <Separator />
          <div class="p-3 space-y-3">
            {#if analysis.results.error}
              <p class="text-sm text-destructive">{analysis.results.error}</p>
            {:else if analysis.results.analyses}
              <!-- Full analysis with sub-analyses -->
              <div class="space-y-2">
                {#if analysis.results.text_statistics}
                  <div class="flex gap-4 text-xs text-muted-foreground">
                    <span>{analysis.results.text_statistics.total_words?.toLocaleString()} words</span>
                    <span>{analysis.results.text_statistics.total_lines?.toLocaleString()} lines</span>
                    <span>{analysis.results.text_statistics.total_stanzas} stanzas</span>
                    <span>Mode: {analysis.results.mode}</span>
                  </div>
                {/if}
                {#each Object.entries(analysis.results.analyses) as [key, value]}
                  <details class="rounded border bg-muted/30">
                    <summary class="cursor-pointer px-3 py-2 text-sm font-medium hover:bg-muted/50">
                      {formatResultKey(key)}
                      {#if typeof value === 'object' && value !== null && 'score' in value}
                        <Badge variant="outline" class="ml-2 text-xs">
                          {Math.round(Number(value.score) * 100)}%
                        </Badge>
                      {/if}
                    </summary>
                    <div class="border-t px-3 py-2">
                      <pre class="max-h-64 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(value, null, 2)}</pre>
                    </div>
                  </details>
                {/each}
              </div>
            {:else}
              <pre class="max-h-96 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(analysis.results, null, 2)}</pre>
            {/if}

            <div class="flex justify-end">
              <Button variant="ghost" size="sm" class="text-destructive" onclick={() => deleteAnalysis(analysis.id)}>
                <Trash2 class="mr-1 h-3 w-3" /> Delete
              </Button>
            </div>
          </div>
        {/if}
      </div>
    {/each}
  </CardContent>
</Card>
