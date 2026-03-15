type Options = {
  delay: number;
};

export class UseClipboard {
  #status = $state<'success' | 'failure'>();
  private delay: number;
  private timeout: ReturnType<typeof setTimeout> | undefined;

  constructor({ delay = 800 }: Partial<Options> = {}) {
    this.delay = delay;
  }

  async copy(text: string) {
    if (this.timeout) {
      this.#status = undefined;
      clearTimeout(this.timeout);
    }
    try {
      await navigator.clipboard.writeText(text);
      this.#status = 'success';
    } catch {
      this.#status = 'failure';
    }
    this.timeout = setTimeout(() => {
      this.#status = undefined;
    }, this.delay);
    return this.#status;
  }

  get copied() {
    return this.#status === 'success';
  }

  get status() {
    return this.#status;
  }
}
