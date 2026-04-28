/**
 * Centralized reader-progress controller.
 *
 * Each format-specific reader (EpubReader, PdfReader, ComicReader) is a dumb
 * event emitter — it reports cursor + percentage and nothing else. The route
 * page constructs one of these and pipes the events through. This module owns
 * the load → save → session-timer → furthest-watermark logic so the route
 * stays a layout component.
 *
 * Differences from the inlined version that lived in reader/[id]/+page.svelte:
 *   - debounced saves (rapid scroll → one PUT, not many)
 *   - visibility-aware session timer survives the unmount flush
 *   - the unmount flush no longer ships ``percentage: 0`` when the location
 *     was a string (the previous dead expression always evaluated to 0).
 */
import { getBookProgress, saveReadProgress, resetFurthestPosition } from '$lib/api/client';
import type { ReadProgress } from '$lib/types/index';

const DEFAULT_DEBOUNCE_MS = 1500;
/** Furthest-prompt threshold: ignore drift smaller than this. */
const FURTHEST_PROMPT_THRESHOLD_PCT = 2;

interface Options {
  bookId: number;
  fileId: number;
  /** Backend ``format`` field — preserved as-is for the wire payload. */
  format: string;
  saveDebounceMs?: number;
}

export class ReaderProgress {
  // Reactive state ------------------------------------------------------------
  loaded = $state(false);
  /** Server-reported initial cursor; used by the reader's first paint. */
  initialCfi = $state<string>('');
  /** Furthest cursor across all devices. */
  furthestCfi = $state<string | undefined>(undefined);
  furthestPct = $state<number>(0);
  /** Last-known current cursor on this device. */
  currentCfi = $state<string | undefined>(undefined);
  currentPct = $state<number>(0);
  /** True between scheduling and finishing a save. */
  saving = $state(false);
  /** True after the user acks/dismisses the furthest prompt. */
  dismissedFurthestPrompt = $state(false);

  // Internal -----------------------------------------------------------------
  #opts: Options;
  #saveTimer: ReturnType<typeof setTimeout> | null = null;
  #lastTimerStart = Date.now();
  #pendingSeconds = 0;
  #isVisible = typeof document !== 'undefined' ? !document.hidden : true;
  #onVisibilityRef = this.#onVisibility.bind(this);
  /** Latest reader-emitted page/total — used when the debounced save fires. */
  #pendingPage: number | null = null;
  #pendingTotal: number | null = null;
  /** Disposed instances refuse further work. */
  #disposed = false;

  constructor(opts: Options) {
    this.#opts = opts;
  }

  /**
   * Whether the route should show a "you read further on another device"
   * banner. Recomputed reactively because it depends on tracked state.
   */
  get showFurthestPrompt(): boolean {
    return (
      !this.dismissedFurthestPrompt
      && !!this.furthestCfi
      && this.furthestCfi !== this.initialCfi
      && this.furthestPct - this.currentPct >= FURTHEST_PROMPT_THRESHOLD_PCT
    );
  }

  /** Load server progress and start the visibility-aware timer. */
  async init(): Promise<void> {
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', this.#onVisibilityRef);
    }
    this.#lastTimerStart = Date.now();
    try {
      const saved = await getBookProgress(this.#opts.bookId);
      if (saved) this.#applyServerSnapshot(saved);
    } catch {
      // Non-critical: missing progress just means start at the top.
    }
    this.loaded = true;
  }

  /** Reader reports its current location string (CFI or "page:N"). */
  setLocation(loc: string | undefined): void {
    this.currentCfi = loc;
  }

  /** Reader reports overall progress. Schedules a debounced save. */
  reportProgress(page: number, total: number, pct: number): void {
    if (this.#disposed) return;
    this.#pendingPage = page;
    this.#pendingTotal = total;
    this.currentPct = pct;
    this.#scheduleSave();
  }

  /**
   * UI: jump to the across-devices furthest position. Does not call the
   * server — the reader is expected to remount on a new initialCfi.
   */
  jumpToFurthest(): boolean {
    if (!this.furthestCfi) return false;
    this.initialCfi = this.furthestCfi;
    this.currentPct = this.furthestPct;
    this.dismissedFurthestPrompt = true;
    return true;
  }

  /** UI: dismiss the furthest banner without jumping. */
  dismissFurthestPrompt(): void {
    this.dismissedFurthestPrompt = true;
  }

  /** UI/admin: reset the furthest watermark to the current cursor. */
  async resetFurthest(): Promise<void> {
    const r = await resetFurthestPosition(this.#opts.bookId);
    this.furthestPct = r.furthest_pct;
    this.furthestCfi = this.currentCfi;
    this.dismissedFurthestPrompt = true;
  }

  /**
   * Force a save now, draining any pending debounce. Idempotent and safe
   * after dispose() — used for the unmount flush.
   */
  async flush(): Promise<void> {
    if (this.#saveTimer) {
      clearTimeout(this.#saveTimer);
      this.#saveTimer = null;
    }
    await this.#save();
  }

  /** Stop listening, drain pending saves, and refuse further input. */
  async dispose(): Promise<void> {
    this.#disposed = true;
    if (typeof document !== 'undefined') {
      document.removeEventListener('visibilitychange', this.#onVisibilityRef);
    }
    await this.flush();
  }

  // Private -------------------------------------------------------------------

  #applyServerSnapshot(p: ReadProgress): void {
    if (p.cfi) this.initialCfi = p.cfi;
    this.currentCfi = p.cfi ?? undefined;
    this.currentPct = p.percentage ?? 0;
    this.furthestPct = p.furthest_percentage ?? 0;
    this.furthestCfi = p.furthest_cfi ?? undefined;
  }

  #scheduleSave(): void {
    const ms = this.#opts.saveDebounceMs ?? DEFAULT_DEBOUNCE_MS;
    if (this.#saveTimer) clearTimeout(this.#saveTimer);
    this.#saveTimer = setTimeout(() => {
      this.#saveTimer = null;
      void this.#save();
    }, ms);
  }

  async #save(): Promise<void> {
    // Without a reported page yet, there's nothing meaningful to send.
    if (this.#pendingPage == null || this.#pendingTotal == null) return;
    const delta = this.#consumeTimerDelta();
    this.saving = true;
    try {
      await saveReadProgress(this.#opts.bookId, {
        current_page: this.#pendingPage + 1,
        total_pages: this.#pendingTotal,
        percentage: this.currentPct,
        file_id: this.#opts.fileId,
        format: this.#opts.format,
        cfi: this.currentCfi,
        time_spent_delta_seconds: delta,
      });
    } catch {
      // Non-critical; the dropped delta is acceptable for a per-second
      // watch counter the user can't observe at that granularity.
    } finally {
      this.saving = false;
    }
  }

  // Session timer ------------------------------------------------------------

  #flushTimer(): void {
    if (!this.#isVisible) return;
    const now = Date.now();
    this.#pendingSeconds += Math.max(0, Math.round((now - this.#lastTimerStart) / 1000));
    this.#lastTimerStart = now;
  }

  #consumeTimerDelta(): number {
    this.#flushTimer();
    const delta = this.#pendingSeconds;
    this.#pendingSeconds = 0;
    this.#lastTimerStart = Date.now();
    return delta;
  }

  #onVisibility(): void {
    if (typeof document === 'undefined') return;
    if (document.hidden) {
      this.#flushTimer();
      this.#isVisible = false;
    } else {
      this.#isVisible = true;
      this.#lastTimerStart = Date.now();
    }
  }
}
