/**
 * Web-Speech-API text-to-speech controller for the EPUB reader.
 *
 * Splits a chapter's visible text into sentence-sized utterances and
 * pipes them through ``window.speechSynthesis``. Per-sentence chunking
 * matters because Chrome silently truncates long utterances after
 * ~250 characters; smaller chunks also let us advance past skipped
 * sentences and surface accurate "currently speaking" state.
 *
 * Designed as a Svelte 5 reactive class so the EpubReader can bind UI
 * directly to ``playing`` / ``paused`` / ``selectedVoice`` / ``rate``.
 *
 * Browser quirks covered:
 *  - Chrome occasionally drops ``onend`` for the last queued utterance,
 *    leaving the engine wedged. The watchdog re-pumps every 4 s.
 *  - Voices load asynchronously on Chromium; ``getVoices()`` returns []
 *    on first call. We listen on ``voiceschanged`` to repopulate.
 */

const SENTENCE_RE = /[^.!?\n]+[.!?]+(?=\s|$)|[^.!?\n]+$/g;

export interface PlayCallbacks {
  /** Called when the queue empties naturally (no skip/stop). */
  onChapterEnd?: () => void;
}

export class TtsController {
  // Reactive state ------------------------------------------------------------
  /** True when the engine has anything queued (playing or paused). */
  active = $state(false);
  /** True when actively speaking (not paused). */
  playing = $state(false);
  paused = $state(false);
  voices = $state<SpeechSynthesisVoice[]>([]);
  selectedVoiceURI = $state<string>('');
  rate = $state(1.0);
  /** Index of the currently-speaking sentence in the active queue. */
  cursor = $state(0);
  total = $state(0);

  // Internal -----------------------------------------------------------------
  #queue: string[] = [];
  #cb: PlayCallbacks = {};
  #watchdog: ReturnType<typeof setInterval> | null = null;
  #voicesHandlerRef = this.#refreshVoices.bind(this);
  #disposed = false;

  constructor() {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;
    this.#refreshVoices();
    window.speechSynthesis.addEventListener('voiceschanged', this.#voicesHandlerRef);
  }

  /** True if the host browser exposes Web Speech at all. */
  static get supported(): boolean {
    return typeof window !== 'undefined' && 'speechSynthesis' in window;
  }

  /**
   * Begin reading ``text``. Drops any previous queue. ``cb.onChapterEnd``
   * fires only when the queue drains naturally — not when stop()/skip()
   * empties it.
   */
  play(text: string, cb: PlayCallbacks = {}): void {
    if (this.#disposed) return;
    if (!TtsController.supported || !text.trim()) return;
    this.stop();
    this.#queue = this.#splitSentences(text);
    this.#cb = cb;
    this.total = this.#queue.length;
    this.cursor = 0;
    if (this.total === 0) return;
    this.active = true;
    this.#pumpWatchdog();
    this.#speakNext();
  }

  pause(): void {
    if (!this.active || this.paused) return;
    window.speechSynthesis.pause();
    this.paused = true;
    this.playing = false;
  }

  resume(): void {
    if (!this.active || !this.paused) return;
    window.speechSynthesis.resume();
    this.paused = false;
    this.playing = true;
  }

  stop(): void {
    this.#queue = [];
    this.cursor = 0;
    this.total = 0;
    this.active = false;
    this.paused = false;
    this.playing = false;
    if (TtsController.supported) window.speechSynthesis.cancel();
    this.#clearWatchdog();
  }

  /** Skip the current utterance — the queue advances on the next pump. */
  skip(): void {
    if (!this.active) return;
    window.speechSynthesis.cancel();
    // ``cancel`` doesn't fire ``end`` on the canceled utterance in some
    // browsers; advance manually so the queue keeps moving.
    this.cursor = Math.min(this.cursor + 1, this.total);
    if (this.cursor < this.total) {
      this.#speakNext();
    } else {
      const cb = this.#cb.onChapterEnd;
      this.stop();
      cb?.();
    }
  }

  setVoice(voiceURI: string): void {
    this.selectedVoiceURI = voiceURI;
  }

  setRate(rate: number): void {
    this.rate = Math.max(0.5, Math.min(2.0, rate));
  }

  dispose(): void {
    this.#disposed = true;
    this.stop();
    if (TtsController.supported) {
      window.speechSynthesis.removeEventListener('voiceschanged', this.#voicesHandlerRef);
    }
  }

  // Private ------------------------------------------------------------------

  #refreshVoices(): void {
    if (!TtsController.supported) return;
    this.voices = window.speechSynthesis.getVoices();
    if (!this.selectedVoiceURI) {
      // Prefer an English default if any voice is exposed.
      const en = this.voices.find((v) => v.lang.toLowerCase().startsWith('en') && v.default);
      const any = this.voices.find((v) => v.default);
      this.selectedVoiceURI = (en ?? any ?? this.voices[0])?.voiceURI ?? '';
    }
  }

  #splitSentences(text: string): string[] {
    const cleaned = text.replace(/\s+/g, ' ').trim();
    if (!cleaned) return [];
    const matches = cleaned.match(SENTENCE_RE) ?? [cleaned];
    return matches.map((s) => s.trim()).filter(Boolean);
  }

  #speakNext(): void {
    if (!this.active || this.cursor >= this.total) return;
    const sentence = this.#queue[this.cursor];
    const u = new SpeechSynthesisUtterance(sentence);
    u.rate = this.rate;
    const voice = this.voices.find((v) => v.voiceURI === this.selectedVoiceURI);
    if (voice) {
      u.voice = voice;
      u.lang = voice.lang;
    }
    u.onstart = () => {
      this.playing = true;
      this.paused = false;
    };
    u.onend = () => {
      // Either we naturally finished or were cancelled; only the natural
      // case advances the cursor here, since skip() already advanced it.
      if (!this.active) return;
      this.cursor += 1;
      if (this.cursor >= this.total) {
        const cb = this.#cb.onChapterEnd;
        this.stop();
        cb?.();
      } else {
        this.#speakNext();
      }
    };
    u.onerror = () => {
      // Skip past the broken utterance rather than wedging the queue.
      this.cursor += 1;
      if (this.cursor >= this.total) {
        this.stop();
      } else {
        this.#speakNext();
      }
    };
    window.speechSynthesis.speak(u);
  }

  #pumpWatchdog(): void {
    this.#clearWatchdog();
    // Chrome wedges its synth queue every ~15 s of continuous playback;
    // a no-op pause/resume keeps it alive. The watchdog is harmless when
    // we're already paused (the user-paused state takes priority).
    this.#watchdog = setInterval(() => {
      if (!this.active || this.paused) return;
      if (window.speechSynthesis.speaking) {
        window.speechSynthesis.pause();
        window.speechSynthesis.resume();
      }
    }, 4000);
  }

  #clearWatchdog(): void {
    if (this.#watchdog) {
      clearInterval(this.#watchdog);
      this.#watchdog = null;
    }
  }
}
