<script lang="ts">
	import { onMount } from "svelte";
	import { motion, AnimatePresence, type Variants } from "motion-sv";
	import { cn } from "$lib/utils/cn";
	import type { Snippet } from "svelte";

	interface Props {
		children: Snippet;
		class?: string;
		duration?: number;
		delay?: number;
		offset?: number;
		direction?: "up" | "down" | "left" | "right";
		inView?: boolean;
		inViewMargin?: string;
		blur?: string;
	}

	let {
		children,
		class: className,
		duration = 0.4,
		delay = 0,
		offset = 6,
		direction = "down",
		inView = false,
		inViewMargin = "-50px",
		blur = "6px",
	}: Props = $props();

	let containerRef: HTMLDivElement | null = $state(null);
	let isInView = $state(false);

	const defaultVariants = $derived.by(() => {
		return {
			hidden: {
				[direction === "left" || direction === "right" ? "x" : "y"]:
					direction === "right" || direction === "down" ? -offset : offset,
				opacity: 0,
				filter: `blur(${blur})`,
			},
			visible: {
				[direction === "left" || direction === "right" ? "x" : "y"]: 0,
				opacity: 1,
				filter: `blur(0px)`,
			},
		} as Variants;
	});

	const shouldAnimate = $derived(!inView || isInView);

	onMount(() => {
		if (!inView) {
			isInView = true;
			return;
		}
		if (!containerRef) return;

		const observer = new IntersectionObserver(
			([entry]) => {
				if (entry.isIntersecting) {
					isInView = true;
					observer.disconnect();
				}
			},
			{ threshold: 0.1, rootMargin: inViewMargin }
		);
		observer.observe(containerRef);
		return () => observer.disconnect();
	});
</script>

<div bind:this={containerRef}>
	<AnimatePresence>
		<motion.div
			initial="hidden"
			animate={shouldAnimate ? "visible" : "hidden"}
			exit="hidden"
			variants={defaultVariants}
			transition={{ delay: 0.04 + delay, duration, ease: "easeOut" }}
			class={cn(className)}
		>
			{@render children()}
		</motion.div>
	</AnimatePresence>
</div>
