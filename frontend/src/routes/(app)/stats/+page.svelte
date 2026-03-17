<script lang="ts">
  import { onMount } from 'svelte';
  import { Card, CardContent, CardHeader, CardTitle } from '$lib/components/ui/card';
  import { Progress } from '$lib/components/ui/progress';
  import { BookOpen, CheckCircle, Clock, BookMarked, BarChart2, CalendarCheck, Flame, TrendingUp, Target, Pencil, X, Check } from 'lucide-svelte';
  // import BlurFade — removed, motion-sv doesn't work in static build
  // import NumberFlow from '@number-flow/svelte'; // removed — causes render issues in static build
  import * as api from '$lib/api/client';
  import type { ReadingStats, ReadingGoal } from '$lib/api/client';

  let stats = $state<ReadingStats | null>(null);
  let loading = $state(true);
  let goal = $state<ReadingGoal | null>(null);
  let editingGoal = $state(false);
  let goalInput = $state('');
  let savingGoal = $state(false);

  onMount(async () => {
    try {
      stats = await api.getReadingStats();
    } catch { /* non-critical */ } finally {
      loading = false;
    }
    try {
      goal = await api.getReadingGoal(currentYear);
    } catch { /* non-critical */ }
  });

  async function saveGoal() {
    const n = parseInt(goalInput);
    if (isNaN(n) || n < 1) return;
    savingGoal = true;
    try {
      goal = await api.setReadingGoal(currentYear, n);
      editingGoal = false;
    } catch { /* non-critical */ } finally { savingGoal = false; }
  }

  function startEditGoal() {
    goalInput = String(goal?.target_books || 12);
    editingGoal = true;
  }

  function formatTime(seconds: number): string {
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    const h = Math.floor(seconds / 3600);
    const m = Math.round((seconds % 3600) / 60);
    return m > 0 ? `${h}h ${m}m` : `${h}h`;
  }

  function formatDate(iso: string | null): string {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  }

  function formatDateShort(iso: string): string {
    return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  }

  // Build heatmap grid: 52 weeks × 7 days (most recent 365 days)
  function buildHeatmap(activityByDay: Array<{ date: string; count: number }>) {
    const map = new Map(activityByDay.map(d => [d.date, d.count]));
    const today = new Date();
    // Start from Sunday of the week 52 weeks ago
    const startDate = new Date(today);
    startDate.setDate(today.getDate() - 364);
    // Align to Sunday
    startDate.setDate(startDate.getDate() - startDate.getDay());

    const weeks: Array<Array<{ date: string; count: number; isFuture: boolean }>> = [];
    let current = new Date(startDate);
    for (let w = 0; w < 53; w++) {
      const week: Array<{ date: string; count: number; isFuture: boolean }> = [];
      for (let d = 0; d < 7; d++) {
        const iso = current.toISOString().slice(0, 10);
        week.push({ date: iso, count: map.get(iso) ?? 0, isFuture: current > today });
        current.setDate(current.getDate() + 1);
      }
      weeks.push(week);
    }
    return weeks;
  }

  function heatColor(count: number): string {
    if (count === 0) return 'bg-muted';
    if (count === 1) return 'bg-emerald-200 dark:bg-emerald-900';
    if (count <= 3) return 'bg-emerald-400 dark:bg-emerald-700';
    if (count <= 6) return 'bg-emerald-500 dark:bg-emerald-500';
    return 'bg-emerald-700 dark:bg-emerald-400';
  }

  // Month labels for heatmap: find the first week of each month
  function monthLabels(weeks: Array<Array<{ date: string }>>) {
    const labels: Array<{ label: string; col: number }> = [];
    let lastMonth = -1;
    weeks.forEach((week, i) => {
      const month = new Date(week[0].date).getMonth();
      if (month !== lastMonth) {
        labels.push({
          label: new Date(week[0].date).toLocaleDateString(undefined, { month: 'short' }),
          col: i,
        });
        lastMonth = month;
      }
    });
    return labels;
  }

  const heatmap = $derived(stats ? buildHeatmap(stats.activity_by_day ?? []) : []);
  const mLabels = $derived(monthLabels(heatmap));

  // Monthly completions bar chart
  const maxCompletions = $derived(
    stats ? Math.max(1, ...( stats.completions_by_month ?? []).map(m => m.count)) : 1
  );

  const currentYear = new Date().getFullYear();
</script>

<div class="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:px-8">
  <div class="mb-8">
    <h1 class="text-3xl font-bold tracking-tight">Reading Stats</h1>
    <p class="mt-1 text-muted-foreground">Your reading activity at a glance</p>
  </div>

  {#if loading}
    <div class="grid grid-cols-2 gap-4 sm:grid-cols-4">
      {#each [1, 2, 3, 4] as _}
        <div class="h-28 animate-pulse rounded-lg bg-muted"></div>
      {/each}
    </div>
  {:else if stats}
    <!-- Summary cards -->
    <div class="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Card>
          <CardContent class="pt-6">
            <div class="flex items-start justify-between">
              <div>
                <p class="text-sm text-muted-foreground">In Library</p>
                <p class="text-3xl font-bold">{stats.total_books}</p>
              </div>
              <BookMarked class="h-5 w-5 text-muted-foreground" />
            </div>
          </CardContent>
        </Card>


        <Card>
          <CardContent class="pt-6">
            <div class="flex items-start justify-between">
              <div>
                <p class="text-sm text-muted-foreground">Completed</p>
                <p class="text-3xl font-bold">{stats.books_completed}</p>
              </div>
              <CheckCircle class="h-5 w-5 text-green-500" />
            </div>
          </CardContent>
        </Card>

      <Card>
        <CardContent class="pt-6">
          <div class="flex items-start justify-between">
            <div>
              <p class="text-sm text-muted-foreground">Reading</p>
              <p class="text-3xl font-bold">{stats.books_reading}</p>
            </div>
            <BookOpen class="h-5 w-5 text-blue-500" />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent class="pt-6">
          <div class="flex items-start justify-between">
            <div>
              <p class="text-sm text-muted-foreground">{currentYear}</p>
              <p class="text-3xl font-bold">{stats.sessions_this_year}</p>
            </div>
            <CalendarCheck class="h-5 w-5 text-violet-500" />
          </div>
          <p class="mt-1 text-xs text-muted-foreground">reads logged</p>
        </CardContent>
      </Card>
    </div>

    <!-- Reading goal -->
    <div class="mt-4">
      <Card>
        <CardContent class="pt-5 pb-5">
          <div class="flex items-center justify-between gap-4">
            <div class="flex items-center gap-3 min-w-0">
              <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10">
                <Target class="h-4.5 w-4.5 text-primary" />
              </div>
              <div class="min-w-0">
                <p class="text-sm font-medium">{currentYear} Reading Goal</p>
                {#if goal && goal.target_books > 0}
                  <p class="text-xs text-muted-foreground">
                    {goal.books_completed} of {goal.target_books} books
                    {#if goal.pct >= 100}
                      <span class="ml-1 text-green-600 font-medium">Goal reached!</span>
                    {/if}
                  </p>
                {:else}
                  <p class="text-xs text-muted-foreground">No goal set for this year</p>
                {/if}
              </div>
            </div>

            <!-- Progress ring + edit -->
            <div class="flex items-center gap-3 shrink-0">
              {#if goal && goal.target_books > 0}
                {@const pct = Math.min(100, goal.pct)}
                {@const r = 18}
                {@const circ = 2 * Math.PI * r}
                {@const dash = circ * pct / 100}
                <div class="relative flex items-center justify-center" title="{pct}%">
                  <svg width="48" height="48" class="-rotate-90">
                    <circle cx="24" cy="24" r={r} fill="none" stroke="currentColor" stroke-width="3" class="text-muted/30" />
                    <circle cx="24" cy="24" r={r} fill="none" stroke="currentColor" stroke-width="3"
                      stroke-dasharray="{dash} {circ - dash}"
                      class="{pct >= 100 ? 'text-green-500' : 'text-primary'} transition-all" />
                  </svg>
                  <span class="absolute text-[10px] font-semibold tabular-nums">{Math.round(pct)}%</span>
                </div>
              {/if}

              {#if editingGoal}
                <div class="flex items-center gap-1">
                  <input
                    type="number"
                    bind:value={goalInput}
                    min="1" max="999"
                    class="w-16 rounded-md border bg-background px-2 py-1 text-sm text-center outline-none focus:ring-1 focus:ring-ring"
                    onkeydown={(e) => { if (e.key === 'Enter') saveGoal(); if (e.key === 'Escape') editingGoal = false; }}
                  />
                  <span class="text-xs text-muted-foreground">books</span>
                  <button onclick={saveGoal} disabled={savingGoal}
                    class="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground disabled:opacity-50">
                    <Check class="h-3.5 w-3.5" />
                  </button>
                  <button onclick={() => editingGoal = false}
                    class="flex h-7 w-7 items-center justify-center rounded-md border hover:bg-accent">
                    <X class="h-3.5 w-3.5" />
                  </button>
                </div>
              {:else}
                <button onclick={startEditGoal}
                  class="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs text-muted-foreground hover:bg-accent hover:text-foreground transition-colors">
                  <Pencil class="h-3 w-3" />
                  {goal && goal.target_books > 0 ? 'Edit' : 'Set goal'}
                </button>
              {/if}
            </div>
          </div>

          {#if goal && goal.target_books > 0}
            <div class="mt-3">
              <div class="h-2 w-full overflow-hidden rounded-full bg-muted">
                <div
                  class="h-full rounded-full transition-all {goal.pct >= 100 ? 'bg-green-500' : 'bg-primary'}"
                  style="width: {Math.min(100, goal.pct)}%"
                ></div>
              </div>
              <div class="mt-1.5 flex justify-between text-[10px] text-muted-foreground">
                <span>0</span>
                <span>{Math.round(goal.target_books / 4)}</span>
                <span>{Math.round(goal.target_books / 2)}</span>
                <span>{Math.round(goal.target_books * 3 / 4)}</span>
                <span>{goal.target_books}</span>
              </div>
            </div>
          {/if}
        </CardContent>
      </Card>
    </div>

    <!-- Streaks + Rating row -->
    <div class="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
      <Card>
        <CardContent class="pt-6">
          <div class="flex items-start justify-between">
            <div>
              <p class="text-sm text-muted-foreground">Current streak</p>
              <p class="text-3xl font-bold">{stats.current_streak ?? 0}</p>
            </div>
            <Flame class="h-5 w-5 text-orange-500" />
          </div>
          <p class="mt-1 text-xs text-muted-foreground">days</p>
        </CardContent>
      </Card>

      <Card>
        <CardContent class="pt-6">
          <div class="flex items-start justify-between">
            <div>
              <p class="text-sm text-muted-foreground">Longest streak</p>
              <p class="text-3xl font-bold">{stats.longest_streak ?? 0}</p>
            </div>
            <TrendingUp class="h-5 w-5 text-amber-500" />
          </div>
          <p class="mt-1 text-xs text-muted-foreground">days</p>
        </CardContent>
      </Card>

      {#if stats.avg_rating != null}
        <Card class="sm:col-span-2">
          <CardContent class="pt-6">
            <p class="text-sm text-muted-foreground mb-2">Rating distribution</p>
            <div class="space-y-1">
              {#each [5, 4, 3, 2, 1] as star}
                {@const count = stats.rating_distribution?.[String(star)] ?? 0}
                {@const total = Object.values(stats.rating_distribution ?? {}).reduce((a, b) => a + b, 0)}
                <div class="flex items-center gap-2 text-xs">
                  <span class="w-4 shrink-0 text-amber-500">{'★'.repeat(star)}</span>
                  <div class="flex-1 rounded-full bg-muted h-1.5 overflow-hidden">
                    <div
                      class="h-full rounded-full bg-amber-400 transition-all"
                      style="width: {total > 0 ? Math.round((count / total) * 100) : 0}%"
                    ></div>
                  </div>
                  <span class="w-5 text-right text-muted-foreground tabular-nums">{count}</span>
                </div>
              {/each}
            </div>
            <p class="mt-2 text-xs text-muted-foreground">avg: {stats.avg_rating?.toFixed(1)} ★</p>
          </CardContent>
        </Card>
      {/if}
    </div>

    <!-- Activity heatmap -->
    {#if (stats.activity_by_day ?? []).length > 0}
      <Card class="mt-6">
        <CardHeader>
          <CardTitle class="text-base">Reading Activity</CardTitle>
        </CardHeader>
        <CardContent>
          <div class="overflow-x-auto">
            <div class="relative min-w-160">
              <!-- Month labels -->
              <div class="mb-1 flex text-[10px] text-muted-foreground" style="margin-left: 0px">
                {#each mLabels as ml}
                  <span
                    class="absolute"
                    style="left: {ml.col * 13}px"
                  >{ml.label}</span>
                {/each}
              </div>
              <!-- Grid -->
              <div class="mt-5 flex gap-0.5">
                {#each heatmap as week}
                  <div class="flex flex-col gap-0.5">
                    {#each week as day}
                      <div
                        class="h-2.5 w-2.5 rounded-sm {day.isFuture ? 'opacity-0' : heatColor(day.count)}"
                        title="{day.date}: {day.count} session{day.count !== 1 ? 's' : ''}"
                      ></div>
                    {/each}
                  </div>
                {/each}
              </div>
              <!-- Legend -->
              <div class="mt-2 flex items-center gap-1 text-[10px] text-muted-foreground justify-end">
                <span>Less</span>
                {#each ['bg-muted', 'bg-emerald-200 dark:bg-emerald-900', 'bg-emerald-400 dark:bg-emerald-700', 'bg-emerald-500', 'bg-emerald-700 dark:bg-emerald-400'] as cls}
                  <div class="h-2.5 w-2.5 rounded-sm {cls}"></div>
                {/each}
                <span>More</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    {/if}

    <!-- Monthly completions chart -->
    {#if (stats.completions_by_month ?? []).length > 0}
      <Card class="mt-6">
        <CardHeader>
          <CardTitle class="text-base">Books Completed by Month</CardTitle>
        </CardHeader>
        <CardContent>
          <div class="flex items-end gap-1.5 h-24">
            {#each stats.completions_by_month ?? [] as m}
              <div class="flex flex-1 flex-col items-center gap-1 min-w-0">
                <div
                  class="w-full rounded-sm bg-primary/70 transition-all"
                  style="height: {m.count === 0 ? '2px' : Math.max(4, Math.round((m.count / maxCompletions) * 80)) + 'px'}"
                  title="{m.month}: {m.count} book{m.count !== 1 ? 's' : ''}"
                ></div>
                <span class="text-[9px] text-muted-foreground truncate w-full text-center">
                  {new Date(m.month + '-01').toLocaleDateString(undefined, { month: 'short' })}
                </span>
              </div>
            {/each}
          </div>
        </CardContent>
      </Card>
    {/if}

    <div class="mt-8 grid gap-6 md:grid-cols-2">
      <!-- Currently reading -->
      <Card>
        <CardHeader>
          <CardTitle class="text-base">Currently Reading</CardTitle>
        </CardHeader>
        <CardContent class="space-y-4">
          {#if stats.currently_reading.length === 0}
            <p class="text-sm text-muted-foreground">Nothing in progress.</p>
          {:else}
            {#each stats.currently_reading as item}
              <a href="/book/{item.id}" class="block hover:opacity-80">
                <div class="flex items-center justify-between text-sm">
                  <div class="min-w-0 flex-1">
                    <p class="truncate font-medium">{item.title}</p>
                    {#if item.author}
                      <p class="truncate text-xs text-muted-foreground">{item.author}</p>
                    {/if}
                  </div>
                  <span class="ml-3 shrink-0 text-xs text-muted-foreground">{item.percentage}%</span>
                </div>
                <Progress value={item.percentage} class="mt-1.5 h-1.5" />
              </a>
            {/each}
          {/if}
        </CardContent>
      </Card>

      <!-- Recently completed -->
      <Card>
        <CardHeader>
          <CardTitle class="text-base">Recently Completed</CardTitle>
        </CardHeader>
        <CardContent class="space-y-3">
          {#if stats.recently_completed.length === 0}
            <p class="text-sm text-muted-foreground">No completed books yet.</p>
          {:else}
            {#each stats.recently_completed as item}
              <a href="/book/{item.id}" class="flex items-center justify-between text-sm hover:opacity-80">
                <div class="min-w-0 flex-1">
                  <p class="truncate font-medium">{item.title}</p>
                  {#if item.author}
                    <p class="truncate text-xs text-muted-foreground">{item.author}</p>
                  {/if}
                </div>
                <span class="ml-3 shrink-0 text-xs text-muted-foreground">
                  {formatDate(item.completed_at)}
                </span>
              </a>
            {/each}
          {/if}
        </CardContent>
      </Card>
    </div>

    <!-- Pages read banner -->
    {#if stats.pages_read > 0}
      <Card class="mt-6">
        <CardContent class="flex items-center gap-4 pt-6">
          <BarChart2 class="h-8 w-8 shrink-0 text-muted-foreground" />
          <div>
            <p class="text-2xl font-bold">{stats.pages_read.toLocaleString()}</p>
            <p class="text-sm text-muted-foreground">total pages read across all books</p>
          </div>
          {#if stats.time_reading_seconds > 0}
            <div class="ml-auto text-right">
              <p class="text-2xl font-bold">{formatTime(stats.time_reading_seconds)}</p>
              <p class="text-sm text-muted-foreground">time read (Kobo)</p>
            </div>
          {/if}
        </CardContent>
      </Card>
    {:else if stats.time_reading_seconds > 0}
      <Card class="mt-6">
        <CardContent class="flex items-center gap-4 pt-6">
          <Clock class="h-8 w-8 shrink-0 text-muted-foreground" />
          <div>
            <p class="text-2xl font-bold">{formatTime(stats.time_reading_seconds)}</p>
            <p class="text-sm text-muted-foreground">time read from Kobo syncs</p>
          </div>
        </CardContent>
      </Card>
    {/if}

    <!-- Reading Log -->
    {#if stats.recent_sessions.length > 0}
      <Card class="mt-6">
        <CardHeader>
          <CardTitle class="text-base">Reading Log</CardTitle>
        </CardHeader>
        <CardContent>
          <div class="space-y-2">
            {#each stats.recent_sessions as s}
              <a href="/book/{s.book_id}" class="flex items-start justify-between rounded-md px-2 py-2 text-sm hover:bg-muted/50 transition-colors">
                <div class="min-w-0 flex-1">
                  <p class="truncate font-medium">{s.title}</p>
                  {#if s.author}
                    <p class="truncate text-xs text-muted-foreground">{s.author}</p>
                  {/if}
                  {#if s.notes}
                    <p class="mt-0.5 truncate text-xs text-muted-foreground italic">"{s.notes}"</p>
                  {/if}
                </div>
                <div class="ml-4 shrink-0 text-right">
                  <p class="text-xs text-muted-foreground">
                    {formatDateShort(s.started_at)}{#if s.finished_at} → {formatDateShort(s.finished_at)}{/if}
                  </p>
                  {#if s.rating}
                    <p class="text-xs text-amber-500">{'★'.repeat(s.rating)}</p>
                  {/if}
                </div>
              </a>
            {/each}
          </div>
        </CardContent>
      </Card>
    {/if}
  {:else}
    <p class="text-muted-foreground">Failed to load stats.</p>
  {/if}
</div>
