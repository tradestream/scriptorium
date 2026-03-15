<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { Button } from "$lib/components/ui/button";
  import { Input } from "$lib/components/ui/input";
  import { ChevronLeft, ChevronRight, ZoomIn, ZoomOut, X } from "lucide-svelte";
  import { downloadBookFile } from "$lib/api/client";

  interface Props {
    bookId: number;
    fileId: number;
    initialPage?: number;
    onProgress?: (page: number, total: number, pct: number) => void;
    onLocationChange?: (location: string) => void;
    onClose?: () => void;
  }

  let { bookId, fileId, initialPage = 1, onProgress, onLocationChange, onClose }: Props = $props();

  let canvas = $state<HTMLCanvasElement | null>(null);
  let pdfDoc: any = $state(null);
  let currentPage = $state(initialPage || 1);
  let totalPages = $state(0);
  let scale = $state(1.5);
  let loading = $state(true);
  let rendering = $state(false);
  let error = $state('');
  let pageInput = $state(String(currentPage));

  onMount(async () => {
    try {
      const blob = await downloadBookFile(bookId, fileId);
      const arrayBuffer = await blob.arrayBuffer();

      const pdfjsLib = await import('pdfjs-dist');
      // Set worker — use CDN for the worker script
      pdfjsLib.GlobalWorkerOptions.workerSrc =
        `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.mjs`;

      pdfDoc = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
      totalPages = pdfDoc.numPages;
      loading = false;
      await renderPage(currentPage);
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load PDF';
      loading = false;
    }
  });

  onDestroy(() => {
    pdfDoc?.destroy();
  });

  async function renderPage(num: number) {
    if (!canvas || !pdfDoc || rendering) return;
    rendering = true;
    try {
      const page = await pdfDoc.getPage(num);
      const viewport = page.getViewport({ scale });
      canvas.height = viewport.height;
      canvas.width = viewport.width;
      const ctx = canvas.getContext('2d')!;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      await page.render({ canvasContext: ctx, viewport }).promise;
      page.cleanup();
    } finally {
      rendering = false;
    }
    const pct = totalPages > 0 ? ((num - 1) / totalPages) * 100 : 0;
    onProgress?.(num, totalPages, pct);
    onLocationChange?.(`page:${num}`);
  }

  async function goToPage(num: number) {
    const clamped = Math.max(1, Math.min(num, totalPages));
    currentPage = clamped;
    pageInput = String(clamped);
    await renderPage(clamped);
  }

  async function prevPage() { if (currentPage > 1) await goToPage(currentPage - 1); }
  async function nextPage() { if (currentPage < totalPages) await goToPage(currentPage + 1); }

  async function zoomIn() { scale = Math.min(scale + 0.25, 4); await renderPage(currentPage); }
  async function zoomOut() { scale = Math.max(scale - 0.25, 0.5); await renderPage(currentPage); }

  function handleKeydown(e: KeyboardEvent) {
    if ((e.target as HTMLElement).tagName === 'INPUT') return;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') nextPage();
    if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') prevPage();
    if (e.key === '+') zoomIn();
    if (e.key === '-') zoomOut();
    if (e.key === 'Escape') onClose?.();
  }

  function handlePageInput(e: KeyboardEvent) {
    if (e.key === 'Enter') {
      const n = parseInt(pageInput, 10);
      if (!isNaN(n)) goToPage(n);
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="flex h-full flex-col bg-background">
  <!-- Toolbar -->
  <div class="flex items-center justify-between border-b bg-background/95 px-4 py-2">
    <Button variant="ghost" size="icon" onclick={onClose}>
      <X class="h-4 w-4" />
    </Button>

    <div class="flex items-center gap-2">
      <Button variant="ghost" size="icon" onclick={prevPage} disabled={currentPage <= 1}>
        <ChevronLeft class="h-4 w-4" />
      </Button>
      <div class="flex items-center gap-1 text-sm">
        <Input
          bind:value={pageInput}
          class="h-7 w-14 text-center text-sm"
          onkeydown={handlePageInput}
        />
        <span class="text-muted-foreground">/ {totalPages}</span>
      </div>
      <Button variant="ghost" size="icon" onclick={nextPage} disabled={currentPage >= totalPages}>
        <ChevronRight class="h-4 w-4" />
      </Button>
    </div>

    <div class="flex items-center gap-1">
      <Button variant="ghost" size="icon" onclick={zoomOut} title="Zoom out">
        <ZoomOut class="h-4 w-4" />
      </Button>
      <span class="min-w-10 text-center text-xs text-muted-foreground">{Math.round(scale * 100)}%</span>
      <Button variant="ghost" size="icon" onclick={zoomIn} title="Zoom in">
        <ZoomIn class="h-4 w-4" />
      </Button>
    </div>
  </div>

  <!-- PDF canvas area -->
  <div class="flex-1 overflow-auto">
    {#if loading}
      <div class="flex h-full items-center justify-center">
        <div class="text-center">
          <div class="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent"></div>
          <p class="mt-3 text-sm text-muted-foreground">Loading PDF...</p>
        </div>
      </div>
    {:else if error}
      <div class="flex h-full items-center justify-center">
        <p class="text-destructive">{error}</p>
      </div>
    {:else}
      <div class="flex min-h-full items-start justify-center p-4">
        <canvas
          bind:this={canvas}
          class="rounded shadow-lg"
          class:opacity-50={rendering}
        ></canvas>
      </div>
    {/if}
  </div>
</div>
