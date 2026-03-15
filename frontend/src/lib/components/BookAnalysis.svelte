<script lang="ts">
  import { Button } from "$lib/components/ui/button";
  import { Card, CardContent, CardHeader, CardTitle } from "$lib/components/ui/card";
  import { Badge } from "$lib/components/ui/badge";
  import { Separator } from "$lib/components/ui/separator";
  import {
    Brain,
    ChevronDown,
    ChevronUp,
    Clock,
    Eye,
    Loader2,
    Plus,
    Settings2,
    Sparkles,
    Trash2,
    Check,
    X,
  } from "lucide-svelte";
  import * as api from "$lib/api/client";
  import type { BookAnalysis, BookAnalysisSummary, AnalysisTemplate, PromptConfig, TextPreview } from "$lib/api/client";

  interface Props {
    bookId: string;
    isAdmin?: boolean;
    esotericEnabled?: boolean;
  }

  let { bookId, isAdmin = false, esotericEnabled = false }: Props = $props();

  let analyses = $state<BookAnalysisSummary[]>([]);
  let templates = $state<AnalysisTemplate[]>([]);
  let expandedId = $state<number | null>(null);
  let expandedContent = $state<BookAnalysis | null>(null);
  let loading = $state(false);
  let generating = $state(false);
  let showTemplateSelect = $state(false);
  let selectedTemplateId = $state<number | null>(null);
  let error = $state("");

  // Esoteric reading edit state (admin)
  let editingEsotericId = $state<number | null>(null);
  let editEsotericText = $state("");
  let savingEsoteric = $state(false);

  // Text preview state
  let showTextPreview = $state(false);
  let textPreview = $state<TextPreview | null>(null);
  let loadingPreview = $state(false);

  // Prompt config state
  let promptConfigs = $state<PromptConfig[]>([]);
  let showPromptSettings = $state(false);
  let editingConfigTemplateId = $state<number | null | undefined>(undefined); // undefined = not editing
  let editSystemPrompt = $state("");
  let editUserPrompt = $state("");
  let editNotes = $state("");
  let savingConfig = $state(false);

  async function loadAnalyses() {
    try {
      analyses = await api.getBookAnalyses(bookId);
    } catch (e) {
      console.error("Failed to load analyses:", e);
    }
  }

  async function loadTemplates() {
    try {
      templates = await api.getAnalysisTemplates();
    } catch (e) {
      console.error("Failed to load templates:", e);
    }
  }

  async function loadPromptConfigs() {
    try {
      promptConfigs = await api.getBookPromptConfigs(bookId);
    } catch (e) {
      console.error("Failed to load prompt configs:", e);
    }
  }

  async function generateAnalysis() {
    generating = true;
    error = "";
    try {
      const template = templates.find((t) => t.id === selectedTemplateId) ?? templates.find((t) => t.is_default);
      const result = await api.createBookAnalysis(bookId, {
        template_id: template?.id,
        title: template?.name ?? "Literary Analysis",
      });
      analyses = [result, ...analyses];
      showTemplateSelect = false;

      // If completed immediately, expand it
      if (result.status === "completed") {
        await toggleExpand(result.id);
      }
    } catch (e) {
      error = e instanceof Error ? e.message : "Failed to generate analysis";
    } finally {
      generating = false;
    }
  }

  async function toggleExpand(analysisId: number) {
    if (expandedId === analysisId) {
      expandedId = null;
      expandedContent = null;
      return;
    }

    loading = true;
    try {
      expandedContent = await api.getBookAnalysis(bookId, String(analysisId));
      expandedId = analysisId;
    } catch (e) {
      console.error("Failed to load analysis:", e);
    } finally {
      loading = false;
    }
  }

  async function saveEsotericReading(analysisId: number) {
    savingEsoteric = true;
    try {
      const updated = await api.setEsotericReading(bookId, String(analysisId), editEsotericText.trim() || null);
      if (expandedContent?.id === analysisId) {
        expandedContent = { ...expandedContent, esoteric_reading: updated.esoteric_reading };
      }
      editingEsotericId = null;
    } catch (e) {
      console.error("Failed to save esoteric reading:", e);
    } finally {
      savingEsoteric = false;
    }
  }

  async function deleteAnalysis(analysisId: number) {
    try {
      await api.deleteBookAnalysis(bookId, String(analysisId));
      analyses = analyses.filter((a) => a.id !== analysisId);
      if (expandedId === analysisId) {
        expandedId = null;
        expandedContent = null;
      }
    } catch (e) {
      console.error("Failed to delete analysis:", e);
    }
  }

  function startEditConfig(templateId: number | null) {
    const existing = promptConfigs.find((c) => c.template_id === templateId);
    editingConfigTemplateId = templateId;
    editSystemPrompt = existing?.custom_system_prompt ?? "";
    editUserPrompt = existing?.custom_user_prompt ?? "";
    editNotes = existing?.notes ?? "";
  }

  function cancelEditConfig() {
    editingConfigTemplateId = undefined;
  }

  async function saveConfig() {
    savingConfig = true;
    try {
      const saved = await api.upsertBookPromptConfig(bookId, {
        template_id: editingConfigTemplateId ?? null,
        custom_system_prompt: editSystemPrompt.trim() || null,
        custom_user_prompt: editUserPrompt.trim() || null,
        notes: editNotes.trim() || null,
      });
      const idx = promptConfigs.findIndex((c) => c.template_id === editingConfigTemplateId);
      if (idx >= 0) {
        promptConfigs[idx] = saved;
      } else {
        promptConfigs = [...promptConfigs, saved];
      }
      editingConfigTemplateId = undefined;
    } catch (e) {
      console.error("Failed to save prompt config:", e);
    } finally {
      savingConfig = false;
    }
  }

  async function deleteConfig(configId: number) {
    try {
      await api.deleteBookPromptConfig(bookId, configId);
      promptConfigs = promptConfigs.filter((c) => c.id !== configId);
    } catch (e) {
      console.error("Failed to delete prompt config:", e);
    }
  }

  async function openTextPreview() {
    showTextPreview = true;
    if (textPreview) return; // Already loaded
    loadingPreview = true;
    try {
      textPreview = await api.getTextPreview(bookId);
    } catch (e) {
      console.error("Failed to load text preview:", e);
    } finally {
      loadingPreview = false;
    }
  }

  // Load on mount
  $effect(() => {
    loadAnalyses();
    loadTemplates();
    if (isAdmin) loadPromptConfigs();
  });
</script>

<Card>
  <CardHeader class="flex flex-row items-center justify-between">
    <div class="flex items-center gap-2">
      <Brain class="h-5 w-5 text-primary" />
      <CardTitle class="text-lg">AI Analysis</CardTitle>
      {#if analyses.length > 0}
        <Badge variant="secondary">{analyses.length}</Badge>
      {/if}
    </div>
    <Button
      size="sm"
      disabled={generating}
      onclick={() => {
        if (templates.length > 1) {
          showTemplateSelect = !showTemplateSelect;
        } else {
          generateAnalysis();
        }
      }}
    >
      {#if generating}
        <Loader2 class="mr-2 h-4 w-4 animate-spin" /> Analyzing...
      {:else}
        <Sparkles class="mr-2 h-4 w-4" /> Analyze
      {/if}
    </Button>
  </CardHeader>

  <CardContent class="space-y-3">
    {#if error}
      <div class="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
        {error}
      </div>
    {/if}

    <!-- Text extraction preview -->
    {#if isAdmin}
      <div class="rounded-md border border-dashed">
        <button
          class="flex w-full items-center justify-between px-3 py-2 text-left text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
          onclick={() => { showTextPreview = !showTextPreview; if (showTextPreview) openTextPreview(); }}
        >
          <span class="flex items-center gap-1.5"><Eye class="h-3.5 w-3.5" /> Extracted Text Preview</span>
          {#if showTextPreview}<ChevronUp class="h-3.5 w-3.5 ml-auto" />{:else}<ChevronDown class="h-3.5 w-3.5 ml-auto" />{/if}
        </button>

        {#if showTextPreview}
          <Separator />
          <div class="p-3 space-y-2">
            {#if loadingPreview}
              <div class="flex justify-center py-4"><Loader2 class="h-4 w-4 animate-spin text-muted-foreground" /></div>
            {:else if textPreview}
              <div class="flex items-center gap-3 text-[11px] text-muted-foreground">
                <span>{textPreview.char_count.toLocaleString()} chars</span>
                <span>·</span>
                <span>{textPreview.word_count.toLocaleString()} words</span>
                {#if textPreview.truncated}<span>· <span class="text-amber-600 dark:text-amber-400">truncated for LLM</span></span>{/if}
              </div>
              <pre class="max-h-48 overflow-y-auto rounded bg-muted p-2 text-[11px] leading-relaxed whitespace-pre-wrap wrap-break-word">{textPreview.preview}{textPreview.truncated ? "\n\n[... truncated ...]" : ""}</pre>
            {:else}
              <p class="text-xs text-muted-foreground py-2">No extractable text found for this book.</p>
            {/if}
          </div>
        {/if}
      </div>
    {/if}

    <!-- Admin: Prompt Settings -->
    {#if isAdmin}
      <div class="rounded-md border border-dashed">
        <button
          class="flex w-full items-center justify-between px-3 py-2 text-left text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
          onclick={() => { showPromptSettings = !showPromptSettings; editingConfigTemplateId = undefined; }}
        >
          <span class="flex items-center gap-1.5"><Settings2 class="h-3.5 w-3.5" /> Prompt Overrides</span>
          <span class="ml-auto flex items-center gap-1.5">
            {#if promptConfigs.length > 0}
              <Badge variant="secondary" class="text-[10px] h-4">{promptConfigs.length}</Badge>
            {/if}
            {#if showPromptSettings}
              <ChevronUp class="h-3.5 w-3.5" />
            {:else}
              <ChevronDown class="h-3.5 w-3.5" />
            {/if}
          </span>
        </button>

        {#if showPromptSettings}
          <Separator />
          <div class="p-3 space-y-3">
            <!-- Existing configs -->
            {#each promptConfigs as cfg (cfg.id)}
              {#if editingConfigTemplateId === cfg.template_id}
                <!-- Edit form -->
                <div class="space-y-2">
                  <p class="text-xs font-medium text-muted-foreground">
                    Editing: {cfg.template_name ?? "Default template"}
                  </p>
                  <div class="space-y-1">
                    <p class="text-xs text-muted-foreground">System prompt (leave blank to use template default)</p>
                    <textarea bind:value={editSystemPrompt} placeholder="Custom system prompt…" rows={3} class="w-full rounded-md border bg-background px-3 py-2 text-xs font-mono focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-y"></textarea>
                  </div>
                  <div class="space-y-1">
                    <p class="text-xs text-muted-foreground">User prompt — use <code class="bg-muted px-1 rounded">{"{text}"}</code> for book content</p>
                    <textarea bind:value={editUserPrompt} placeholder="Custom user prompt…" rows={4} class="w-full rounded-md border bg-background px-3 py-2 text-xs font-mono focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-y"></textarea>
                  </div>
                  <div class="space-y-1">
                    <p class="text-xs text-muted-foreground">Notes (internal)</p>
                    <textarea bind:value={editNotes} placeholder="Notes…" rows={2} class="w-full rounded-md border bg-background px-3 py-2 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-y"></textarea>
                  </div>
                  <div class="flex gap-2">
                    <Button size="sm" class="h-7 text-xs" disabled={savingConfig} onclick={saveConfig}>
                      {#if savingConfig}<Loader2 class="mr-1 h-3 w-3 animate-spin" />{:else}<Check class="mr-1 h-3 w-3" />{/if}
                      Save
                    </Button>
                    <Button variant="outline" size="sm" class="h-7 text-xs" onclick={cancelEditConfig}>
                      <X class="mr-1 h-3 w-3" /> Cancel
                    </Button>
                  </div>
                </div>
              {:else}
                <div class="flex items-start justify-between gap-2 rounded-md bg-muted/40 px-2.5 py-2">
                  <div class="min-w-0">
                    <p class="text-xs font-medium">{cfg.template_name ?? "Default template"}</p>
                    {#if cfg.custom_system_prompt}
                      <p class="mt-0.5 truncate text-[11px] text-muted-foreground">sys: {cfg.custom_system_prompt}</p>
                    {/if}
                    {#if cfg.custom_user_prompt}
                      <p class="mt-0.5 truncate text-[11px] text-muted-foreground">user: {cfg.custom_user_prompt}</p>
                    {/if}
                    {#if cfg.notes}
                      <p class="mt-0.5 truncate text-[11px] italic text-muted-foreground">{cfg.notes}</p>
                    {/if}
                  </div>
                  <div class="flex shrink-0 gap-1">
                    <Button variant="ghost" size="sm" class="h-6 w-6 p-0" onclick={() => startEditConfig(cfg.template_id)}>
                      <Settings2 class="h-3 w-3" />
                    </Button>
                    <Button variant="ghost" size="sm" class="h-6 w-6 p-0 text-destructive hover:text-destructive" onclick={() => deleteConfig(cfg.id)}>
                      <Trash2 class="h-3 w-3" />
                    </Button>
                  </div>
                </div>
              {/if}
            {/each}

            <!-- Add new override -->
            {#if editingConfigTemplateId === undefined}
              <div class="space-y-1.5">
                <p class="text-xs text-muted-foreground">Add override for:</p>
                <div class="flex flex-wrap gap-1.5">
                  {#each templates as t}
                    {#if !promptConfigs.some((c) => c.template_id === t.id)}
                      <button
                        class="rounded border px-2 py-0.5 text-xs hover:bg-accent transition-colors"
                        onclick={() => startEditConfig(t.id)}
                      >{t.name}</button>
                    {/if}
                  {/each}
                </div>
              </div>
            {/if}
          </div>
        {/if}
      </div>
    {/if}

    <!-- Template selector -->
    {#if showTemplateSelect}
      <div class="space-y-2 rounded-md border bg-muted/50 p-3">
        <p class="text-sm font-medium">Choose analysis type:</p>
        {#each templates as template}
          <button
            class="flex w-full items-start gap-3 rounded-md p-2 text-left text-sm transition-colors hover:bg-accent"
            onclick={() => {
              selectedTemplateId = template.id;
              generateAnalysis();
            }}
          >
            <Sparkles class="mt-0.5 h-4 w-4 shrink-0 text-primary" />
            <div>
              <p class="font-medium">{template.name}</p>
              {#if template.description}
                <p class="text-xs text-muted-foreground">{template.description}</p>
              {/if}
            </div>
            {#if template.is_default}
              <Badge variant="outline" class="ml-auto shrink-0 text-xs">Default</Badge>
            {/if}
          </button>
        {/each}
        <Button variant="outline" size="sm" class="w-full" onclick={() => (showTemplateSelect = false)}>
          Cancel
        </Button>
      </div>
    {/if}

    <!-- Analysis list -->
    {#if analyses.length === 0 && !generating}
      <p class="py-4 text-center text-sm text-muted-foreground">
        No analyses yet. Click "Analyze" to generate an AI-powered literary analysis of this book.
      </p>
    {/if}

    {#each analyses as analysis (analysis.id)}
      <div class="rounded-md border">
        <button
          class="flex w-full items-center justify-between p-3 text-left text-sm transition-colors hover:bg-muted/50"
          onclick={() => toggleExpand(analysis.id)}
        >
          <div class="flex items-center gap-2">
            {#if analysis.status === "running"}
              <Loader2 class="h-4 w-4 animate-spin text-primary" />
            {:else if analysis.status === "failed"}
              <Badge variant="destructive" class="text-xs">Failed</Badge>
            {:else}
              <Brain class="h-4 w-4 text-primary" />
            {/if}
            <span class="font-medium">{analysis.title}</span>
          </div>
          <div class="flex items-center gap-2">
            {#if analysis.model_used}
              <span class="text-xs text-muted-foreground">{analysis.model_used}</span>
            {/if}
            <span class="flex items-center gap-1 text-xs text-muted-foreground">
              <Clock class="h-3 w-3" />
              {new Date(analysis.created_at).toLocaleDateString()}
            </span>
            {#if expandedId === analysis.id}
              <ChevronUp class="h-4 w-4" />
            {:else}
              <ChevronDown class="h-4 w-4" />
            {/if}
          </div>
        </button>

        {#if expandedId === analysis.id}
          <Separator />
          <div class="p-4">
            {#if loading}
              <div class="flex items-center justify-center py-8">
                <Loader2 class="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            {:else if expandedContent}
              {#if expandedContent.status === "failed"}
                <p class="text-sm text-destructive">{expandedContent.error_message}</p>
              {:else}
                <div class="prose prose-sm max-w-none dark:prose-invert">
                  <pre class="whitespace-pre-wrap font-sans text-sm leading-relaxed">{expandedContent.content}</pre>
                </div>

                <!-- Esoteric reading -->
                {#if esotericEnabled && expandedContent.esoteric_reading}
                  <div class="mt-4 rounded-md border border-violet-200 bg-violet-50/50 dark:border-violet-800 dark:bg-violet-950/20 p-3 space-y-2">
                    <p class="text-xs font-semibold text-violet-700 dark:text-violet-300 uppercase tracking-wide">Esoteric Reading</p>
                    <pre class="whitespace-pre-wrap font-sans text-sm leading-relaxed text-violet-900 dark:text-violet-100">{expandedContent.esoteric_reading}</pre>
                  </div>
                {/if}

                <!-- Admin: edit esoteric reading -->
                {#if isAdmin && esotericEnabled}
                  {#if editingEsotericId === analysis.id}
                    <div class="mt-3 space-y-2">
                      <p class="text-xs font-medium text-muted-foreground">Esoteric reading (admin)</p>
                      <textarea
                        bind:value={editEsotericText}
                        placeholder="Hidden-meaning interpretation…"
                        rows={5}
                        class="w-full rounded-md border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-y"
                      ></textarea>
                      <div class="flex gap-2">
                        <Button size="sm" class="h-7 text-xs" disabled={savingEsoteric} onclick={() => saveEsotericReading(analysis.id)}>
                          {#if savingEsoteric}<Loader2 class="mr-1 h-3 w-3 animate-spin" />{:else}<Check class="mr-1 h-3 w-3" />{/if} Save
                        </Button>
                        <Button variant="outline" size="sm" class="h-7 text-xs" onclick={() => (editingEsotericId = null)}>
                          <X class="mr-1 h-3 w-3" /> Cancel
                        </Button>
                      </div>
                    </div>
                  {:else}
                    <button
                      class="mt-2 text-xs text-violet-600 hover:text-violet-700 underline"
                      onclick={() => { editingEsotericId = analysis.id; editEsotericText = expandedContent?.esoteric_reading ?? ""; }}
                    >{expandedContent.esoteric_reading ? "Edit esoteric reading" : "Add esoteric reading"}</button>
                  {/if}
                {/if}
              {/if}
              <Separator class="my-3" />
              <div class="flex items-center justify-between text-xs text-muted-foreground">
                <span>
                  {#if expandedContent.token_count}
                    {expandedContent.token_count.toLocaleString()} tokens
                  {/if}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  class="h-7 text-xs text-destructive hover:text-destructive"
                  onclick={() => deleteAnalysis(analysis.id)}
                >
                  <Trash2 class="mr-1 h-3 w-3" /> Delete
                </Button>
              </div>
            {/if}
          </div>
        {/if}
      </div>
    {/each}
  </CardContent>
</Card>
