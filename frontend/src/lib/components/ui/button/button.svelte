<script lang="ts">
  import { cn } from "$lib/utils/cn";
  import type { ButtonVariant, ButtonSize } from "./index";
  import type { Snippet } from "svelte";
  import type { HTMLButtonAttributes, HTMLAnchorAttributes } from "svelte/elements";

  type Props = {
    variant?: ButtonVariant;
    size?: ButtonSize;
    children?: Snippet;
    class?: string;
    href?: string;
  } & (HTMLButtonAttributes | HTMLAnchorAttributes);

  let {
    variant = "default",
    size = "default",
    children,
    class: className,
    href,
    ...restProps
  }: Props = $props();

  const variants: Record<ButtonVariant, string> = {
    default: "bg-primary text-primary-foreground shadow-sm hover:bg-primary/90",
    destructive: "bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90",
    outline: "border border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground",
    secondary: "bg-secondary text-secondary-foreground shadow-sm hover:bg-secondary/80",
    ghost: "hover:bg-accent hover:text-accent-foreground",
    link: "text-primary underline-offset-4 hover:underline",
  };

  const sizes: Record<ButtonSize, string> = {
    default: "h-9 px-4 py-2",
    sm: "h-8 rounded-md px-3 text-xs",
    lg: "h-10 rounded-md px-8",
    icon: "h-9 w-9",
  };

  const baseClass = cn(
    "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50",
    variants[variant],
    sizes[size],
    className
  );
</script>

{#if href}
  <a {href} class={baseClass} {...(restProps as HTMLAnchorAttributes)}>
    {#if children}{@render children()}{/if}
  </a>
{:else}
  <button class={baseClass} {...(restProps as HTMLButtonAttributes)}>
    {#if children}{@render children()}{/if}
  </button>
{/if}
