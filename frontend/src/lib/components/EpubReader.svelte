<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { Button } from "$lib/components/ui/button";
  import { ChevronLeft, ChevronRight, Settings, X, Minus, Plus, AlignJustify, Columns2, Moon, Sun, List, Volume2, Pause, Play, SkipForward, Square } from "lucide-svelte";
  import { downloadBookFile } from "$lib/api/client";
  import { TtsController, QWEN_VOICES, ELEVENLABS_VOICES } from "$lib/reader/tts.svelte";
  import { Transcription } from "$lib/components/ai-elements/transcription";

  interface Props {
    bookId: number;
    fileId: number;
    initialCfi?: string;
    initialPage?: number;
    onProgress?: (page: number, total: number, pct: number) => void;
    onLocationChange?: (location: string) => void;
    onClose?: () => void;
  }

  let { bookId, fileId, initialCfi = '', initialPage = 0, onProgress, onLocationChange, onClose }: Props = $props();

  let container = $state<HTMLElement | null>(null);
  let rendition: any = $state(null);
  let book: any = $state(null);
  let currentPage = $state(0);
  let totalPages = $state(0);
  let loading = $state(true);
  let error = $state('');
  let showSettings = $state(false);
  let showToc = $state(false);
  let showTts = $state(false);
  let toc = $state<Array<{ label: string; href: string; level: number }>>([]);
  let chapterTitle = $state('');

  // TTS controller — Web Speech API. Stays inert until the user opens
  // the panel, so books that don't use TTS pay zero cost.
  const tts = new TtsController();

  // Reader settings (BookLore-inspired)
  let fontSize = $state(100);
  let lineHeight = $state(1.5);
  let justify = $state(true);
  let columns = $state(1);
  let darkMode = $state(typeof window !== 'undefined' && document.documentElement.classList.contains('dark'));
  let flow = $state<'paginated' | 'scrolled'>('paginated');

  // Touch/swipe state
  let touchStartX = 0;
  let touchStartY = 0;
  const SWIPE_THRESHOLD = 50;

  onMount(async () => {
    if (!container) return;
    try {
      const blob = await downloadBookFile(bookId, fileId);
      const arrayBuffer = await blob.arrayBuffer();

      const { default: Epub } = await import('epubjs');
      book = Epub();
      await book.open(arrayBuffer, "binary");

      rendition = book.renderTo(container, {
        width: '100%',
        height: '100%',
        spread: columns > 1 ? 'auto' : 'none',
        flow: flow,
        minSpreadWidth: columns > 1 ? 800 : 99999,
        allowScriptedContent: false,
      });

      // Defense in depth: EPUB XHTML can contain inline <script> tags that
      // epubjs's allowScriptedContent flag doesn't strip. Set a strict iframe
      // sandbox so anything epubjs renders from the EPUB cannot run scripts,
      // submit forms, open popups, or navigate the top frame. allow-same-origin
      // is required so epubjs can read contentDocument for layout/positioning.
      rendition.hooks.render.register((view: any) => {
        try {
          view?.iframe?.setAttribute('sandbox', 'allow-same-origin');
        } catch { /* non-critical */ }
      });

      // Apply initial styles
      applyStyles();

      await book.ready;
      await book.locations.generate(1024);
      totalPages = book.locations.total;

      rendition.on('relocated', (location: any) => {
        const pg = book.locations.locationFromCfi(location.start.cfi);
        currentPage = typeof pg === 'number' ? pg : 0;
        const pct = totalPages > 0 ? (currentPage / totalPages) * 100 : 0;
        onProgress?.(currentPage, totalPages, pct);
        if (location.start?.cfi) onLocationChange?.(location.start.cfi);

        // Update chapter title
        try {
          const section = book.spine.get(location.start.href);
          if (section) {
            const navItem = book.navigation?.toc?.find((t: any) => t.href?.includes(section.href));
            chapterTitle = navItem?.label?.trim() || '';
          }
        } catch { /* non-critical */ }
      });

      // Restore position. A stored CFI can be invalid for this EPUB
      // (cross-book leak, format change, malformed save) — epub.js then
      // throws "No Section Found" and the reader stays blank. Fall back
      // to the start so the book still renders.
      try {
        if (initialCfi) {
          await rendition.display(initialCfi);
        } else if (initialPage > 0 && book.locations.cfiFromLocation) {
          const cfi = book.locations.cfiFromLocation(initialPage);
          await rendition.display(cfi);
        } else {
          await rendition.display();
        }
      } catch (cfiErr) {
        console.warn('initialCfi/page invalid for this EPUB; opening at start:', cfiErr);
        await rendition.display();
      }

      // Load table of contents
      try {
        const nav = book.navigation;
        if (nav?.toc) {
          const flatToc: Array<{ label: string; href: string; level: number }> = [];
          function walkToc(items: any[], level: number) {
            for (const item of items) {
              flatToc.push({ label: item.label?.trim() || '', href: item.href, level });
              if (item.subitems?.length) walkToc(item.subitems, level + 1);
            }
          }
          walkToc(nav.toc, 0);
          toc = flatToc;
        }
      } catch { /* non-critical */ }

      loading = false;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load book';
      loading = false;
    }
  });

  onDestroy(() => {
    tts.dispose();
    rendition?.destroy();
    book?.destroy();
  });

  /** Pull the visible chapter's text from the rendered iframe. */
  function currentChapterText(): string {
    try {
      const view = rendition?.manager?.views?._views?.[0];
      const doc: Document | undefined = view?.document ?? view?.iframe?.contentDocument;
      return doc?.body?.textContent ?? '';
    } catch {
      return '';
    }
  }

  function ttsPlayCurrent() {
    const text = currentChapterText();
    if (!text.trim()) return;
    tts.play(text, {
      onChapterEnd: () => {
        // Drive the reader forward; the new ``relocated`` event will
        // re-trigger this callback if the user keeps TTS active.
        rendition?.next().then(() => {
          // Defer the read of the next chapter slightly so epub.js has
          // time to populate the new view's DOM.
          setTimeout(() => {
            const next = currentChapterText();
            if (next.trim()) ttsPlayCurrent();
          }, 250);
        });
      },
    });
  }

  function prevPage() { rendition?.prev(); }
  function nextPage() { rendition?.next(); }

  function goToChapter(href: string) {
    rendition?.display(href);
    showToc = false;
  }

  function applyStyles() {
    if (!rendition) return;
    rendition.themes.default({
      'body': {
        'font-size': `${fontSize}% !important`,
        'line-height': `${lineHeight} !important`,
        'text-align': justify ? 'justify' : 'start',
        '-webkit-hyphens': justify ? 'auto' : 'none',
        'hyphens': justify ? 'auto' : 'none',
      },
      'p': {
        'line-height': `${lineHeight} !important`,
      },
    });

    if (darkMode) {
      rendition.themes.override('color', '#e0e0e0');
      rendition.themes.override('background', '#1a1a1a');
    } else {
      rendition.themes.override('color', '#1a1a1a');
      rendition.themes.override('background', '#fafaf9');
    }
  }

  function changeFontSize(delta: number) {
    fontSize = Math.max(70, Math.min(200, fontSize + delta));
    applyStyles();
  }

  function changeLineHeight(delta: number) {
    lineHeight = Math.max(1.0, Math.min(3.0, +(lineHeight + delta).toFixed(1)));
    applyStyles();
  }

  function toggleJustify() {
    justify = !justify;
    applyStyles();
  }

  function toggleDarkMode() {
    darkMode = !darkMode;
    applyStyles();
  }

  function toggleColumns() {
    columns = columns === 1 ? 2 : 1;
    if (rendition) {
      rendition.spread(columns > 1 ? 'auto' : 'none');
    }
  }

  function toggleFlow() {
    flow = flow === 'paginated' ? 'scrolled' : 'paginated';
    if (rendition) {
      rendition.flow(flow);
    }
  }

  // Touch/swipe handlers
  function handleTouchStart(e: TouchEvent) {
    touchStartX = e.touches[0].clientX;
    touchStartY = e.touches[0].clientY;
  }

  function handleTouchEnd(e: TouchEvent) {
    const deltaX = e.changedTouches[0].clientX - touchStartX;
    const deltaY = e.changedTouches[0].clientY - touchStartY;
    // Only trigger if horizontal swipe is dominant
    if (Math.abs(deltaX) > SWIPE_THRESHOLD && Math.abs(deltaX) > Math.abs(deltaY)) {
      if (deltaX < 0) nextPage();
      else prevPage();
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown' || e.key === ' ') { e.preventDefault(); nextPage(); }
    if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') { e.preventDefault(); prevPage(); }
    if (e.key === 'Escape') onClose?.();
  }

  const pct = $derived(totalPages > 0 ? Math.round((currentPage / totalPages) * 100) : 0);
</script>

<svelte:window onkeydown={handleKeydown} />

<div
  class="relative flex h-full flex-col {darkMode ? 'bg-[#1a1a1a] text-[#e0e0e0]' : 'bg-[#fafaf9] text-[#1a1a1a]'}"
  ontouchstart={handleTouchStart}
  ontouchend={handleTouchEnd}
>
  <!-- Toolbar -->
  <div class="flex items-center justify-between border-b px-2 py-1.5 {darkMode ? 'border-white/10 bg-[#1a1a1a]/95' : 'border-black/10 bg-[#fafaf9]/95'} backdrop-blur">
    <div class="flex items-center gap-0.5 shrink-0">
      <Button variant="ghost" size="icon" class="h-8 w-8 {darkMode ? 'text-white/70 hover:text-white' : ''}" onclick={onClose}>
        <X class="h-4 w-4" />
      </Button>
      <Button variant="ghost" size="icon" class="h-8 w-8 {darkMode ? 'text-white/70 hover:text-white' : ''}" onclick={() => { showToc = !showToc; showSettings = false; }} title="Table of contents">
        <List class="h-4 w-4" />
      </Button>
    </div>
    <div class="flex flex-col items-center gap-0 min-w-0 flex-1 mx-2 overflow-hidden">
      {#if chapterTitle}
        <span class="text-[11px] truncate max-w-full {darkMode ? 'text-white/50' : 'text-black/50'}">{chapterTitle}</span>
      {/if}
      {#if totalPages > 0}
        <span class="text-[11px] tabular-nums {darkMode ? 'text-white/40' : 'text-black/40'}">{pct}%</span>
      {/if}
    </div>
    <div class="flex items-center gap-0.5 shrink-0">
      {#if TtsController.supported}
        <Button
          variant="ghost"
          size="icon"
          class="h-8 w-8 {tts.active ? (darkMode ? 'text-emerald-400' : 'text-emerald-600') : darkMode ? 'text-white/70 hover:text-white' : ''}"
          onclick={() => { showTts = !showTts; showSettings = false; showToc = false; }}
          title="Text-to-speech"
        >
          <Volume2 class="h-4 w-4" />
        </Button>
      {/if}
      <Button variant="ghost" size="icon" class="h-8 w-8 {darkMode ? 'text-white/70 hover:text-white' : ''}" onclick={() => { showSettings = !showSettings; showToc = false; showTts = false; }}>
        <Settings class="h-4 w-4" />
      </Button>
    </div>
  </div>

  <!-- TOC panel -->
  {#if showToc}
    <div class="border-b overflow-y-auto max-h-[50vh] {darkMode ? 'border-white/10 bg-[#222]' : 'border-black/10 bg-white'}">
      {#if toc.length === 0}
        <p class="px-4 py-6 text-xs text-center {darkMode ? 'text-white/40' : 'text-black/40'}">No table of contents available</p>
      {:else}
        {#each toc as item}
          <button
            class="block w-full text-left px-4 py-2 text-xs hover:bg-black/5 {darkMode ? 'hover:bg-white/5' : ''} border-b {darkMode ? 'border-white/5' : 'border-black/5'}"
            style="padding-left: {16 + item.level * 16}px"
            onclick={() => goToChapter(item.href)}
          >
            {item.label}
          </button>
        {/each}
      {/if}
    </div>
  {/if}

  <!-- Settings panel -->
  {#if showSettings}
    <div class="border-b px-3 py-3 space-y-3 {darkMode ? 'border-white/10 bg-[#222]' : 'border-black/10 bg-white'}">
      <!-- Font size + Line height in one row -->
      <div class="flex items-center gap-4">
        <div class="flex items-center gap-1.5">
          <span class="text-[10px] {darkMode ? 'text-white/40' : 'text-black/40'}">Aa</span>
          <button onclick={() => changeFontSize(-10)} class="rounded border p-1 {darkMode ? 'border-white/20 hover:bg-white/10' : 'border-black/20 hover:bg-black/5'}">
            <Minus class="h-3 w-3" />
          </button>
          <span class="text-[10px] tabular-nums w-8 text-center">{fontSize}%</span>
          <button onclick={() => changeFontSize(10)} class="rounded border p-1 {darkMode ? 'border-white/20 hover:bg-white/10' : 'border-black/20 hover:bg-black/5'}">
            <Plus class="h-3 w-3" />
          </button>
        </div>
        <div class="flex items-center gap-1.5">
          <span class="text-[10px] {darkMode ? 'text-white/40' : 'text-black/40'}">↕</span>
          <button onclick={() => changeLineHeight(-0.1)} class="rounded border p-1 {darkMode ? 'border-white/20 hover:bg-white/10' : 'border-black/20 hover:bg-black/5'}">
            <Minus class="h-3 w-3" />
          </button>
          <span class="text-[10px] tabular-nums w-6 text-center">{lineHeight}</span>
          <button onclick={() => changeLineHeight(0.1)} class="rounded border p-1 {darkMode ? 'border-white/20 hover:bg-white/10' : 'border-black/20 hover:bg-black/5'}">
            <Plus class="h-3 w-3" />
          </button>
        </div>
      </div>
      <!-- Toggles row — wrap on narrow screens -->
      <div class="flex flex-wrap items-center gap-1.5">
        <button onclick={toggleJustify} class="rounded border px-2 py-1 text-[10px] {justify ? (darkMode ? 'border-white/30 bg-white/10' : 'border-black/30 bg-black/5') : (darkMode ? 'border-white/10' : 'border-black/10')}">
          Justify
        </button>
        <button onclick={toggleColumns} class="rounded border px-2 py-1 text-[10px] {columns > 1 ? (darkMode ? 'border-white/30 bg-white/10' : 'border-black/30 bg-black/5') : (darkMode ? 'border-white/10' : 'border-black/10')}">
          {columns > 1 ? '2-up' : '1-up'}
        </button>
        <button onclick={toggleFlow} class="rounded border px-2 py-1 text-[10px] {darkMode ? 'border-white/10' : 'border-black/10'}">
          {flow === 'paginated' ? 'Paged' : 'Scroll'}
        </button>
        <button onclick={toggleDarkMode} class="rounded border px-2 py-1 text-[10px] {darkMode ? 'border-white/10' : 'border-black/10'}">
          {#if darkMode}<Sun class="h-3 w-3" />{:else}<Moon class="h-3 w-3" />{/if}
        </button>
      </div>
    </div>
  {/if}

  <!-- TTS panel -->
  {#if showTts}
    <div class="border-b px-3 py-3 space-y-2 {darkMode ? 'border-white/10 bg-[#222]' : 'border-black/10 bg-white'}">
      <div class="flex items-center gap-1.5">
        {#if !tts.active}
          <button
            onclick={ttsPlayCurrent}
            class="flex items-center gap-1 rounded border px-2 py-1 text-[11px] font-medium {darkMode ? 'border-white/20 hover:bg-white/10' : 'border-black/20 hover:bg-black/5'}"
            title="Read this chapter"
          >
            <Play class="h-3 w-3" /> Read
          </button>
        {:else if tts.paused}
          <button
            onclick={() => tts.resume()}
            class="flex items-center gap-1 rounded border px-2 py-1 text-[11px] font-medium {darkMode ? 'border-white/20 hover:bg-white/10' : 'border-black/20 hover:bg-black/5'}"
          >
            <Play class="h-3 w-3" /> Resume
          </button>
        {:else}
          <button
            onclick={() => tts.pause()}
            class="flex items-center gap-1 rounded border px-2 py-1 text-[11px] font-medium {darkMode ? 'border-white/20 hover:bg-white/10' : 'border-black/20 hover:bg-black/5'}"
          >
            <Pause class="h-3 w-3" /> Pause
          </button>
        {/if}
        <button
          onclick={() => tts.skip()}
          disabled={!tts.active}
          class="flex items-center gap-1 rounded border px-2 py-1 text-[11px] {darkMode ? 'border-white/20 hover:bg-white/10' : 'border-black/20 hover:bg-black/5'} disabled:opacity-40"
          title="Skip sentence"
        >
          <SkipForward class="h-3 w-3" />
        </button>
        <button
          onclick={() => tts.stop()}
          disabled={!tts.active}
          class="flex items-center gap-1 rounded border px-2 py-1 text-[11px] {darkMode ? 'border-white/20 hover:bg-white/10' : 'border-black/20 hover:bg-black/5'} disabled:opacity-40"
          title="Stop"
        >
          <Square class="h-3 w-3" />
        </button>
        {#if tts.active}
          <span class="ml-2 text-[10px] tabular-nums {darkMode ? 'text-white/50' : 'text-black/50'}">
            {tts.cursor + 1} / {tts.total}
          </span>
        {/if}
      </div>

      <!-- Sentence progress bar — fits the chunked-utterance model better
           than a media-style scrub bar would. -->
      {#if tts.active && tts.total > 0}
        <div class="h-1 w-full overflow-hidden rounded-full {darkMode ? 'bg-white/10' : 'bg-black/10'}">
          <div
            class="h-full bg-primary transition-all duration-300"
            style="width: {((tts.cursor + 1) / tts.total) * 100}%"
          ></div>
        </div>
      {/if}
      <!-- Backend toggle — only the buttons whose backend is wired up
           and whose host capability is present appear. ``Browser`` is
           hidden on hosts without Web Speech (older Safari, embedded
           WebViews) so cloud-only is a clean experience. -->
      {#if TtsController.webSupported || tts.qwenAvailable || tts.elevenlabsAvailable || tts.localAvailable}
        <div class="flex items-center gap-1.5 flex-wrap">
          {#if TtsController.webSupported}
            <button
              onclick={() => tts.setBackend('web')}
              class="rounded border px-2 py-1 text-[10px] {tts.backend === 'web' ? (darkMode ? 'border-white/30 bg-white/10' : 'border-black/30 bg-black/5') : (darkMode ? 'border-white/10' : 'border-black/10')}"
              title="Browser-native TTS (free, instant, lower quality)"
            >
              Browser
            </button>
          {/if}
          {#if tts.localAvailable}
            <button
              onclick={() => tts.setBackend('local')}
              class="rounded border px-2 py-1 text-[10px] {tts.backend === 'local' ? (darkMode ? 'border-white/30 bg-white/10' : 'border-black/30 bg-black/5') : (darkMode ? 'border-white/10' : 'border-black/10')}"
              title="Qwen3-TTS running locally on Apple Silicon (free, ~500ms)"
            >
              Local
            </button>
          {/if}
          {#if tts.qwenAvailable}
            <button
              onclick={() => tts.setBackend('qwen')}
              class="rounded border px-2 py-1 text-[10px] {tts.backend === 'qwen' ? (darkMode ? 'border-white/30 bg-white/10' : 'border-black/30 bg-black/5') : (darkMode ? 'border-white/10' : 'border-black/10')}"
              title="Qwen3-TTS via DashScope"
            >
              Qwen
            </button>
          {/if}
          {#if tts.elevenlabsAvailable}
            <button
              onclick={() => tts.setBackend('elevenlabs')}
              class="rounded border px-2 py-1 text-[10px] {tts.backend === 'elevenlabs' ? (darkMode ? 'border-white/30 bg-white/10' : 'border-black/30 bg-black/5') : (darkMode ? 'border-white/10' : 'border-black/10')}"
              title="ElevenLabs (studio quality, paid per character)"
            >
              ElevenLabs
            </button>
          {/if}
        </div>
      {/if}
      <div class="flex items-center gap-2 flex-wrap">
        {#if tts.backend === 'web'}
          {#if tts.voices.length > 0}
            <select
              class="rounded border bg-transparent px-1.5 py-1 text-[11px] {darkMode ? 'border-white/20 text-white' : 'border-black/20'}"
              value={tts.selectedVoiceURI}
              onchange={(e) => tts.setVoice((e.currentTarget as HTMLSelectElement).value)}
            >
              {#each tts.voices as v (v.voiceURI)}
                <option value={v.voiceURI}>{v.name} ({v.lang})</option>
              {/each}
            </select>
          {:else}
            <span class="text-[10px] italic {darkMode ? 'text-white/40' : 'text-black/40'}">No voices yet — try refreshing</span>
          {/if}
        {:else}
          {@const voiceList = tts.backend === 'elevenlabs' ? ELEVENLABS_VOICES : QWEN_VOICES}
          <select
            class="rounded border bg-transparent px-1.5 py-1 text-[11px] {darkMode ? 'border-white/20 text-white' : 'border-black/20'}"
            value={tts.currentCloudVoice}
            onchange={(e) => tts.setCloudVoice((e.currentTarget as HTMLSelectElement).value)}
          >
            {#each voiceList as v (v.id)}
              <option value={v.id}>{v.label}</option>
            {/each}
          </select>
        {/if}
        <label class="flex items-center gap-1.5 text-[10px] {darkMode ? 'text-white/50' : 'text-black/50'}">
          rate
          <input
            type="range"
            min="0.5"
            max="2"
            step="0.1"
            class="w-16"
            value={tts.rate}
            oninput={(e) => tts.setRate(parseFloat((e.currentTarget as HTMLInputElement).value))}
          />
          <span class="w-7 tabular-nums text-right">{tts.rate.toFixed(1)}×</span>
        </label>
      </div>

      <!-- Transcription — every sentence in the active queue. Click any
           one to jump TTS playback there. Only meaningful while playing. -->
      {#if tts.active && tts.sentences.length > 0}
        <div class="max-h-40 overflow-y-auto rounded border p-2 {darkMode ? 'border-white/10 bg-black/30' : 'border-black/10 bg-white/40'}">
          <Transcription
            sentences={tts.sentences}
            cursor={tts.cursor}
            onSeek={(i) => tts.seekTo(i)}
          />
        </div>
      {/if}
    </div>
  {/if}

  <!-- Reader area -->
  <div class="relative flex-1 overflow-hidden">
    {#if loading}
      <div class="flex h-full items-center justify-center">
        <div class="text-center">
          <div class="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-current border-t-transparent opacity-40"></div>
          <p class="mt-3 text-sm opacity-50">Loading book...</p>
        </div>
      </div>
    {:else if error}
      <div class="flex h-full items-center justify-center">
        <p class="text-destructive">{error}</p>
      </div>
    {:else}
      <!-- Click navigation zones (desktop) -->
      <button
        class="absolute left-0 top-0 z-10 h-full w-[15%] cursor-pointer opacity-0 hover:opacity-100 flex items-center justify-start pl-2"
        onclick={prevPage}
        aria-label="Previous page"
      >
        <ChevronLeft class="h-8 w-8 opacity-30" />
      </button>
      <button
        class="absolute right-0 top-0 z-10 h-full w-[15%] cursor-pointer opacity-0 hover:opacity-100 flex items-center justify-end pr-2"
        onclick={nextPage}
        aria-label="Next page"
      >
        <ChevronRight class="h-8 w-8 opacity-30" />
      </button>
    {/if}

    <!-- epub.js mounts here — constrained to ~680px like Medium for comfortable reading -->
    <div bind:this={container} class="h-full w-full mx-auto" style="max-width: 720px; padding: 0 2rem;"></div>
  </div>

  <!-- Progress bar at bottom -->
  {#if totalPages > 0 && !loading}
    <div class="h-0.5 w-full {darkMode ? 'bg-white/5' : 'bg-black/5'}">
      <div
        class="h-full transition-all {darkMode ? 'bg-white/20' : 'bg-black/15'}"
        style="width: {pct}%"
      ></div>
    </div>
  {/if}
</div>
