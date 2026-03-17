<script lang="ts">
	import { motion, useScroll } from "motion-sv";
	import { cn } from "$lib/utils/cn";

	interface Props {
		class?: string;
	}

	let { class: className }: Props = $props();

	let scroll = $derived(useScroll());
</script>

<motion.div
	class={cn(
		"fixed inset-x-0 top-0 z-50 h-1 origin-left bg-gradient-to-r from-primary via-primary/70 to-primary/40",
		className
	)}
	style={{ scaleX: scroll.scrollYProgress }}
/>
