<script lang="ts">
	import { motion } from "motion-sv";
	import { cn } from "$lib/utils/cn";

	interface Props {
		size?: number;
		duration?: number;
		delay?: number;
		colorFrom?: string;
		colorTo?: string;
		class?: string;
		reverse?: boolean;
		initialOffset?: number;
		borderWidth?: number;
	}

	let {
		class: className,
		size = 50,
		delay = 0,
		duration = 6,
		colorFrom = "#ffaa40",
		colorTo = "#9c40ff",
		reverse = false,
		initialOffset = 0,
		borderWidth = 1,
	}: Props = $props();

	const containerStyle = $derived(`--border-beam-width: ${borderWidth}px;`);

	const beamStyle = $derived({
		width: size,
		offsetPath: `rect(0 auto auto 0 round ${size}px)`,
		"--color-from": colorFrom,
		"--color-to": colorTo,
	} as any);
</script>

<div
	class="pointer-events-none absolute inset-0 rounded-[inherit]"
	style={containerStyle}
>
	<motion.div
		class={cn(
			"absolute aspect-square bg-gradient-to-l from-[var(--color-from)] via-[var(--color-to)] to-transparent",
			className
		)}
		style={beamStyle}
		initial={{ offsetDistance: `${initialOffset}%` }}
		animate={{
			offsetDistance: reverse
				? [`${100 - initialOffset}%`, `${-initialOffset}%`]
				: [`${initialOffset}%`, `${100 + initialOffset}%`],
		}}
		transition={{
			repeat: Infinity,
			ease: "linear",
			duration,
			delay: -delay,
		}}
	/>
</div>
