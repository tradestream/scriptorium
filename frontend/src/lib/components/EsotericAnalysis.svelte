<script lang="ts">
  import { Button } from "$lib/components/ui/button";
  import { Card, CardContent, CardHeader, CardTitle } from "$lib/components/ui/card";
  import { Badge } from "$lib/components/ui/badge";
  import { Separator } from "$lib/components/ui/separator";
  import { Input } from "$lib/components/ui/input";
  import {
    Eye,
    EyeOff,
    Loader2,
    Search,
    Target,
    BarChart3,
    AlertTriangle,
    ChevronDown,
    ChevronUp,
    Trash2,
    Crosshair,
    Scale,
    Repeat,
    Users,
    HelpCircle,
    Cpu,
    Quote,
    PieChart,
    BookOpen,
    GitBranch,
    Bold,
    BookmarkMinus,
    Footprints,
    Layers,
    Drama,
  } from "lucide-svelte";
  import * as api from "$lib/api/client";
  import type { ComputationalAnalysis, ComputationalAnalysisRequest } from "$lib/api/client";

  interface Props {
    bookId: string;
  }

  let { bookId }: Props = $props();

  let analyses = $state<ComputationalAnalysis[]>([]);
  let loading = $state(false);
  let running = $state(false);
  let expandedId = $state<number | null>(null);
  let showConfig = $state(false);

  // Config state
  let keywordsInput = $state("justice, truth, god, gods, fate, piety, wisdom, nature, law, virtue");
  let entitiesInput = $state("");
  let selectedType = $state<ComputationalAnalysisRequest["analysis_type"]>("full");

  const analysisGroups = [
    {
      label: "Core Esoteric",
      types: [
        { value: "full" as const, label: "Full Esoteric Analysis", icon: Eye, description: "Run all core Straussian tools" },
        { value: "engine_v2" as const, label: "Engine v2 (All Tools)", icon: Cpu, description: "Comprehensive computational analysis" },
        { value: "loud_silence" as const, label: "Loud Silences", icon: EyeOff, description: "Where keywords conspicuously vanish" },
        { value: "contradiction" as const, label: "Contradiction Hunter", icon: AlertTriangle, description: "Entity sentiment dissonance across sections" },
        { value: "center" as const, label: "Center Locator", icon: Crosshair, description: "Physical center of the text" },
        { value: "exoteric_esoteric" as const, label: "Exo/Eso Ratio", icon: Scale, description: "Pious vs. subversive language ratio" },
      ],
    },
    {
      label: "Rhetorical & Linguistic",
      types: [
        { value: "repetition_variation" as const, label: "Repetition with Variation", icon: Repeat, description: "Repeated formulations with subtle changes" },
        { value: "hedging_language" as const, label: "Hedging Language", icon: HelpCircle, description: "Qualifiers, conditionals, and epistemic hedges" },
        { value: "conditional_language" as const, label: "Conditional Language", icon: GitBranch, description: "If/then patterns and hypotheticals" },
        { value: "emphasis_quotation" as const, label: "Emphasis & Quotation", icon: Bold, description: "Italics, bold, and quotation patterns" },
      ],
    },
    {
      label: "Structural",
      types: [
        { value: "section_proportion" as const, label: "Section Proportions", icon: PieChart, description: "Relative size and balance of sections" },
        { value: "first_last_words" as const, label: "First & Last Words", icon: BookOpen, description: "Opening and closing words of each section" },
        { value: "parenthetical_footnote" as const, label: "Parentheticals & Footnotes", icon: BookmarkMinus, description: "Asides, parenthetical remarks, and footnotes" },
        { value: "structural_obscurity" as const, label: "Structural Obscurity", icon: Layers, description: "Unusual organization and buried passages" },
        { value: "epigraph" as const, label: "Epigraphs", icon: Quote, description: "Epigraphs and their relationship to the text" },
      ],
    },
    {
      label: "Voice & Audience",
      types: [
        { value: "audience_differentiation" as const, label: "Audience Differentiation", icon: Users, description: "Signals aimed at different reader levels" },
        { value: "self_reference" as const, label: "Self-Reference", icon: Footprints, description: "Author references to own work and method" },
        { value: "disreputable_mouthpiece" as const, label: "Disreputable Mouthpieces", icon: Drama, description: "Dangerous ideas voiced through flawed characters" },
      ],
    },
  ];

  // Flat list for backwards compat
  const analysisTypes = analysisGroups.flatMap((g) => g.types);

  async function loadAnalyses() {
    try {
      analyses = await api.getComputationalAnalyses(bookId);
    } catch (e) {
      console.error("Failed to load esoteric analyses:", e);
    }
  }

  async function runAnalysis() {
    running = true;
    try {
      const keywords = keywordsInput.split(",").map((k) => k.trim()).filter(Boolean);
      const entities = entitiesInput.split(",").map((e) => e.trim()).filter(Boolean);

      const result = await api.runComputationalAnalysis(bookId, {
        analysis_type: selectedType,
        keywords,
        entities,
      });

      analyses = [result, ...analyses];
      showConfig = false;
      expandedId = result.id;
    } catch (e) {
      console.error("Failed to run analysis:", e);
    } finally {
      running = false;
    }
  }

  async function deleteAnalysis(analysisId: number) {
    try {
      await api.deleteComputationalAnalysis(bookId, String(analysisId));
      analyses = analyses.filter((a) => a.id !== analysisId);
      if (expandedId === analysisId) expandedId = null;
    } catch (e) {
      console.error("Failed to delete:", e);
    }
  }

  function getTypeIcon(type: string) {
    return analysisTypes.find((t) => t.value === type)?.icon ?? Eye;
  }

  function getTypeLabel(type: string) {
    return analysisTypes.find((t) => t.value === type)?.label ?? type;
  }

  $effect(() => {
    loadAnalyses();
  });
</script>

<Card>
  <CardHeader class="flex flex-row items-center justify-between">
    <div class="flex items-center gap-2">
      <Eye class="h-5 w-5 text-primary" />
      <CardTitle class="text-lg">Esoteric Analysis</CardTitle>
      <Badge variant="outline" class="text-xs">Computational</Badge>
    </div>
    <Button
      size="sm"
      variant="outline"
      disabled={running}
      onclick={() => (showConfig = !showConfig)}
    >
      {#if running}
        <Loader2 class="mr-2 h-4 w-4 animate-spin" /> Running...
      {:else}
        <Search class="mr-2 h-4 w-4" /> Configure & Run
      {/if}
    </Button>
  </CardHeader>

  <CardContent class="space-y-3">
    <!-- Config panel -->
    {#if showConfig}
      <div class="space-y-3 rounded-md border bg-muted/50 p-4">
        <p class="text-sm font-medium">Analysis Configuration</p>

        <!-- Type selector (grouped) -->
        {#each analysisGroups as group}
          <div>
            <p class="mb-1.5 text-xs font-medium text-muted-foreground">{group.label}</p>
            <div class="grid grid-cols-2 gap-1.5 sm:grid-cols-3">
              {#each group.types as type}
                {@const Icon = type.icon}
                <button
                  class="flex items-start gap-2 rounded-md border p-2 text-left text-xs transition-colors {selectedType === type.value ? 'border-primary bg-primary/5' : 'hover:bg-accent'}"
                  onclick={() => (selectedType = type.value)}
                >
                  <Icon class="mt-0.5 h-3 w-3 shrink-0" />
                  <div>
                    <p class="font-medium">{type.label}</p>
                    <p class="text-muted-foreground">{type.description}</p>
                  </div>
                </button>
              {/each}
            </div>
          </div>
        {/each}

        <!-- Keywords -->
        <div class="space-y-1">
          <label for="keywords" class="text-xs font-medium">Keywords to track (comma-separated)</label>
          <Input id="keywords" bind:value={keywordsInput} placeholder="justice, truth, god, fate, piety" class="text-sm" />
        </div>

        <!-- Entities (for contradiction hunter) -->
        {#if selectedType === "full" || selectedType === "contradiction"}
          <div class="space-y-1">
            <label for="entities" class="text-xs font-medium">Entities to track sentiment (comma-separated)</label>
            <Input id="entities" bind:value={entitiesInput} placeholder="Odysseus, Athena, Zeus, Penelope" class="text-sm" />
          </div>
        {/if}

        <div class="flex gap-2">
          <Button size="sm" onclick={runAnalysis} disabled={running}>
            {#if running}<Loader2 class="mr-2 h-4 w-4 animate-spin" />{/if}
            Run Analysis
          </Button>
          <Button size="sm" variant="outline" onclick={() => (showConfig = false)}>Cancel</Button>
        </div>
      </div>
    {/if}

    <!-- Results list -->
    {#if analyses.length === 0 && !running}
      <p class="py-4 text-center text-sm text-muted-foreground">
        No esoteric analyses yet. Configure keywords and entities, then run
        computational analysis to detect loud silences, contradictions, structural
        centers, and exoteric/esoteric language ratios.
      </p>
    {/if}

    {#each analyses as analysis (analysis.id)}
      {@const TypeIcon = getTypeIcon(analysis.analysis_type)}
      <div class="rounded-md border">
        <button
          class="flex w-full items-center justify-between p-3 text-left text-sm transition-colors hover:bg-muted/50"
          onclick={() => (expandedId = expandedId === analysis.id ? null : analysis.id)}
        >
          <div class="flex items-center gap-2">
            <TypeIcon class="h-4 w-4 text-primary" />
            <span class="font-medium">{getTypeLabel(analysis.analysis_type)}</span>
            {#if analysis.status === "failed"}
              <Badge variant="destructive" class="text-xs">Failed</Badge>
            {/if}
          </div>
          <div class="flex items-center gap-2 text-xs text-muted-foreground">
            <span>{new Date(analysis.created_at).toLocaleDateString()}</span>
            {#if expandedId === analysis.id}
              <ChevronUp class="h-4 w-4" />
            {:else}
              <ChevronDown class="h-4 w-4" />
            {/if}
          </div>
        </button>

        {#if expandedId === analysis.id}
          <Separator />
          <div class="space-y-4 p-4">
            <!-- Loud Silences -->
            {#if analysis.results.loud_silences}
              {@const ls = analysis.results.loud_silences}
              <div>
                <h4 class="mb-2 flex items-center gap-2 text-sm font-semibold">
                  <EyeOff class="h-4 w-4" /> Loud Silences
                  {#if ls.silences?.length > 0}
                    <Badge variant="destructive" class="text-xs">{ls.silences.length} found</Badge>
                  {/if}
                </h4>
                {#if ls.silences?.length > 0}
                  <div class="space-y-1">
                    {#each ls.silences.slice(0, 10) as silence}
                      <div class="flex items-center gap-2 rounded bg-destructive/5 px-2 py-1 text-xs">
                        <Badge variant={silence.severity === "loud" ? "destructive" : "outline"} class="text-xs">
                          {silence.severity}
                        </Badge>
                        <span>
                          <strong>"{silence.keyword}"</strong> absent from <strong>{silence.section}</strong>
                          (avg: {silence.expected_avg}, actual: {silence.actual})
                        </span>
                      </div>
                    {/each}
                  </div>
                {:else}
                  <p class="text-xs text-muted-foreground">No loud silences detected.</p>
                {/if}

                <!-- Heatmap data table -->
                {#if ls.heatmap_data?.length > 0}
                  <div class="mt-2 overflow-x-auto">
                    <table class="w-full text-xs">
                      <thead>
                        <tr class="border-b">
                          <th class="p-1 text-left font-medium">Section</th>
                          {#each Object.keys(ls.heatmap_data[0]).filter((k) => k !== "section") as kw}
                            <th class="p-1 text-center font-medium">{kw}</th>
                          {/each}
                        </tr>
                      </thead>
                      <tbody>
                        {#each ls.heatmap_data as row}
                          <tr class="border-b">
                            <td class="p-1 font-medium">{row.section}</td>
                            {#each Object.keys(row).filter((k) => k !== "section") as kw}
                              {@const val = row[kw]}
                              <td
                                class="p-1 text-center"
                                style="background-color: hsl(0, {Math.min(val * 20, 80)}%, {100 - Math.min(val * 5, 40)}%)"
                              >
                                {val}
                              </td>
                            {/each}
                          </tr>
                        {/each}
                      </tbody>
                    </table>
                  </div>
                {/if}
              </div>
            {/if}

            <!-- Contradictions -->
            {#if analysis.results.contradictions}
              {@const ct = analysis.results.contradictions}
              <div>
                <h4 class="mb-2 flex items-center gap-2 text-sm font-semibold">
                  <AlertTriangle class="h-4 w-4" /> Sentiment Dissonances
                  {#if ct.dissonances?.length > 0}
                    <Badge variant="secondary" class="text-xs">{ct.dissonances.length} entities</Badge>
                  {/if}
                </h4>
                {#if ct.dissonances?.length > 0}
                  {#each ct.dissonances as d}
                    <div class="mb-2 rounded border p-2 text-xs">
                      <p class="font-medium">{d.entity} ({d.total_mentions} mentions)</p>
                      <div class="mt-1 flex gap-4">
                        <span class="text-green-600">+{d.positive_count} positive (avg {d.avg_positive_score})</span>
                        <span class="text-red-600">-{d.negative_count} negative (avg {d.avg_negative_score})</span>
                        <span class="font-mono">delta: {d.delta}</span>
                      </div>
                    </div>
                  {/each}
                {:else}
                  <p class="text-xs text-muted-foreground">No significant sentiment dissonances detected.</p>
                {/if}
              </div>
            {/if}

            <!-- Centers -->
            {#if analysis.results.centers}
              {@const cn = analysis.results.centers}
              <div>
                <h4 class="mb-2 flex items-center gap-2 text-sm font-semibold">
                  <Crosshair class="h-4 w-4" /> Structural Center
                  <span class="font-normal text-muted-foreground">
                    ({cn.total_words?.toLocaleString()} words, {cn.total_lines?.toLocaleString()} lines)
                  </span>
                </h4>
                {#if cn.center_passage}
                  <div class="rounded border bg-muted/50 p-3">
                    <p class="mb-1 text-xs font-medium text-muted-foreground">
                      Lines {cn.center_line_range?.[0]}–{cn.center_line_range?.[1]} (global center):
                    </p>
                    <pre class="whitespace-pre-wrap font-serif text-xs leading-relaxed">{cn.center_passage}</pre>
                  </div>
                {/if}
              </div>
            {/if}

            <!-- Exoteric / Esoteric Ratio -->
            {#if analysis.results.exoteric_esoteric_ratio}
              {@const eer = analysis.results.exoteric_esoteric_ratio}
              <div>
                <h4 class="mb-2 flex items-center gap-2 text-sm font-semibold">
                  <Scale class="h-4 w-4" /> Exoteric / Esoteric Ratio
                  <span class="font-normal text-muted-foreground">
                    (Pious: {eer.overall_pious} | Subversive: {eer.overall_subversive})
                  </span>
                </h4>

                <!-- Flagged sections -->
                {#if eer.flagged_sections?.length > 0}
                  <div class="mb-2 space-y-1">
                    {#each eer.flagged_sections as flagged}
                      <div class="rounded border border-yellow-500/30 bg-yellow-500/5 p-2 text-xs">
                        <p class="font-medium">{flagged.section_label}</p>
                        {#each flagged.reasons as reason}
                          <p class="text-muted-foreground">— {reason}</p>
                        {/each}
                      </div>
                    {/each}
                  </div>
                {/if}

                <!-- Ratio bars -->
                {#if eer.section_ratios?.length > 0}
                  <div class="space-y-1">
                    {#each eer.section_ratios as ratio}
                      <div class="flex items-center gap-2 text-xs">
                        <span class="w-24 truncate font-medium">{ratio.section_label}</span>
                        <div class="flex h-4 flex-1 overflow-hidden rounded">
                          {#if ratio.total_tagged > 0}
                            <div
                              class="bg-blue-400"
                              style="width: {ratio.pious_ratio * 100}%"
                              title="Pious: {ratio.pious_count}"
                            />
                            <div
                              class="bg-red-400"
                              style="width: {ratio.subversive_ratio * 100}%"
                              title="Subversive: {ratio.subversive_count}"
                            />
                          {:else}
                            <div class="w-full bg-muted" />
                          {/if}
                        </div>
                        <span class="w-16 text-right font-mono text-muted-foreground">
                          {ratio.dominant === "pious" ? "P" : ratio.dominant === "subversive" ? "S" : "N"}
                          {ratio.total_tagged}
                        </span>
                      </div>
                    {/each}
                    <div class="mt-1 flex gap-4 text-xs text-muted-foreground">
                      <span class="flex items-center gap-1"><span class="inline-block h-2 w-2 rounded bg-blue-400"></span> Pious/Exoteric</span>
                      <span class="flex items-center gap-1"><span class="inline-block h-2 w-2 rounded bg-red-400"></span> Subversive/Esoteric</span>
                    </div>
                  </div>
                {/if}
              </div>
            {/if}

            <Separator />
            <div class="flex justify-end">
              <Button
                variant="ghost"
                size="sm"
                class="h-7 text-xs text-destructive hover:text-destructive"
                onclick={() => deleteAnalysis(analysis.id)}
              >
                <Trash2 class="mr-1 h-3 w-3" /> Delete
              </Button>
            </div>
          </div>
        {/if}
      </div>
    {/each}
  </CardContent>
</Card>
