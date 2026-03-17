<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { X } from "lucide-svelte";
  import { Button } from "$lib/components/ui/button";

  interface Props {
    onScan: (isbn: string) => void;
    onClose: () => void;
  }

  let { onScan, onClose }: Props = $props();

  let containerEl = $state<HTMLElement | null>(null);
  let error = $state('');
  let status = $state<'loading' | 'scanning' | 'manual'>('loading');
  let manualInput = $state('');
  let wasmScanner: any = null;

  function isIsbnLike(data: string): boolean {
    const clean = data.replace(/[-\s]/g, '');
    return /^\d{10,13}$/.test(clean) || /^\d{9}[Xx]$/.test(clean);
  }

  function handleDetection(data: string) {
    const clean = data.replace(/[-\s]/g, '');
    if (isIsbnLike(clean)) {
      cleanup();
      onScan(clean);
    }
  }

  async function loadWasmGlue(): Promise<boolean> {
    if ((window as any).Module?._scan_image_rgba) return true;

    return new Promise((resolve) => {
      if (!(window as any).Module) {
        (window as any).Module = {};
      }
      const script = document.createElement('script');
      script.src = '/a.out.js';
      script.onload = () => {
        const check = () => {
          if ((window as any).Module?._scan_image_rgba) {
            resolve(true);
          } else {
            setTimeout(check, 50);
          }
        };
        setTimeout(check, 100);
        setTimeout(() => resolve(!!(window as any).Module?._scan_image_rgba), 5000);
      };
      script.onerror = () => resolve(false);
      document.head.appendChild(script);
    });
  }

  async function startScanner() {
    if (!containerEl) return;

    try {
      const wasmReady = await loadWasmGlue();
      if (!wasmReady) {
        error = 'Failed to load barcode scanner engine';
        status = 'manual';
        return;
      }

      const { BarcodeScanner } = await import('web-wasm-barcode-reader');

      wasmScanner = new BarcodeScanner({
        container: containerEl,
        onDetect: (result: { symbol: string; data: string }) => {
          handleDetection(result.data);
        },
        onError: (err: Error) => {
          error = err.message;
          status = 'manual';
        },
        scanInterval: 150,
        beepOnDetect: true,
        facingMode: 'environment',
      });

      await wasmScanner.start();
      status = 'scanning';
    } catch (e) {
      error = e instanceof Error ? e.message : 'Camera access denied or unavailable';
      status = 'manual';
    }
  }

  function cleanup() {
    if (wasmScanner) {
      try { wasmScanner.stop(); } catch { /* ignore */ }
      wasmScanner = null;
    }
  }

  onMount(() => {
    // Wait a tick for containerEl to bind, then start
    requestAnimationFrame(() => startScanner());
  });

  onDestroy(cleanup);

  function submitManual() {
    const v = manualInput.trim().replace(/[-\s]/g, '');
    if (v) {
      cleanup();
      onScan(v);
    }
  }

  function switchToManual() {
    cleanup();
    status = 'manual';
  }
</script>

<div class="fixed inset-0 z-50 flex flex-col bg-black">
  <!-- Header -->
  <div class="flex items-center justify-between px-4 py-3 bg-black/80 text-white z-10">
    <h2 class="text-sm font-medium">Scan ISBN Barcode</h2>
    <button onclick={() => { cleanup(); onClose(); }} class="rounded p-1 hover:bg-white/10">
      <X class="h-5 w-5" />
    </button>
  </div>

  {#if status === 'manual'}
    <!-- Manual ISBN entry fallback -->
    <div class="flex flex-1 flex-col items-center justify-center gap-4 px-6">
      <p class="text-center text-sm text-white/70">
        {error || 'Enter the ISBN from the book\'s barcode or copyright page:'}
      </p>
      <input
        type="text"
        bind:value={manualInput}
        placeholder="ISBN (10 or 13 digits)"
        class="w-full max-w-xs rounded-md border border-white/20 bg-white/10 px-4 py-3 text-center text-lg text-white placeholder:text-white/30 outline-none focus:ring-2 focus:ring-primary"
        onkeydown={(e) => { if (e.key === 'Enter') submitManual(); }}
        inputmode="numeric"
      />
      <Button onclick={submitManual} disabled={!manualInput.trim()} class="min-w-32">
        Look up
      </Button>
    </div>
  {:else}
    <!-- Scanner container — WASM scanner mounts video + overlay here -->
    <div bind:this={containerEl} class="flex-1 relative overflow-hidden">
      {#if status === 'loading'}
        <div class="absolute inset-0 flex items-center justify-center">
          <p class="text-sm text-white/50">Starting camera…</p>
        </div>
      {/if}
    </div>

    <!-- Manual fallback link -->
    <div class="bg-black/80 px-4 py-3 text-center z-10">
      <button onclick={switchToManual} class="text-xs text-white/50 hover:text-white/80">
        Enter ISBN manually instead
      </button>
    </div>
  {/if}
</div>
