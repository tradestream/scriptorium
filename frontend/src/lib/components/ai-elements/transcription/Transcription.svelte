<!--
  Sentence-indexed transcription view, ported from Vercel AI Elements
  (packages/elements/src/transcription.tsx) and adapted for our chunked
  TTS model. The original keys highlight on time ranges; ours keys on
  sentence index because Web Speech and our cloud backends both play one
  utterance at a time without exposing a continuous timeline.

  Renders the full chapter text as clickable spans. The active sentence
  (``cursor``) is highlighted; past sentences are dimmed; future ones
  dimmer still. Click a sentence → ``onSeek(index)`` so the controller
  can jump there.
-->
<script lang="ts">
  import { cn } from '$lib/utils/cn';
  import type { Snippet } from 'svelte';

  interface Props {
    sentences: string[];
    /** Index of the sentence currently being spoken (0-based). */
    cursor: number;
    /** Called when the user clicks a sentence; controller should jump there. */
    onSeek?: (index: number) => void;
    class?: string;
    /** Optional render override — receives ``(text, state)`` per sentence. */
    children?: Snippet<[{ text: string; index: number; isActive: boolean; isPast: boolean }]>;
  }

  let { sentences, cursor, onSeek, class: className, children }: Props = $props();
</script>

<div class={cn('flex flex-wrap gap-1 text-sm leading-relaxed', className)} data-slot="transcription">
  {#each sentences as text, i (i)}
    {@const isActive = i === cursor}
    {@const isPast = i < cursor}
    {#if children}
      {@render children({ text, index: i, isActive, isPast })}
    {:else}
      <button
        type="button"
        class={cn(
          'inline text-left rounded px-0.5 transition-colors',
          isActive && 'text-primary font-medium bg-primary/10',
          isPast && !isActive && 'text-muted-foreground/70',
          !isActive && !isPast && 'text-muted-foreground/40',
          onSeek ? 'cursor-pointer hover:text-foreground hover:bg-muted' : 'cursor-default',
        )}
        data-active={isActive}
        data-index={i}
        data-slot="transcription-segment"
        onclick={() => onSeek?.(i)}
      >
        {text}
      </button>
    {/if}
  {/each}
</div>
