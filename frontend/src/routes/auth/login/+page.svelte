<script lang="ts">
  import { goto } from "$app/navigation";
  import { page } from "$app/state";
  import { setAuthToken, getOidcConfig } from "$lib/api/client";
  import * as api from "$lib/api/client";
  import { Button } from "$lib/components/ui/button";
  import { Input } from "$lib/components/ui/input";
  import { Separator } from "$lib/components/ui/separator";
  import { onMount } from "svelte";
  import type { LoginRequest } from "$lib/types/index";

  let username = $state("");
  let password = $state("");
  let error = $state(
    page.url.searchParams.get("error") === "oidc_failed"
      ? "SSO sign-in failed. Please try again."
      : ""
  );
  let loading = $state(false);
  let oidcEnabled = $state(false);

  onMount(async () => {
    try {
      const cfg = await getOidcConfig();
      oidcEnabled = cfg.enabled;
    } catch { /* non-critical */ }
  });

  async function handleSubmit(e: SubmitEvent) {
    e.preventDefault();
    error = "";
    loading = true;

    try {
      const credentials: LoginRequest = { username, password };
      const result = await api.login(credentials);
      if (result.access_token) {
        setAuthToken(result.access_token);
        await goto("/");
      }
    } catch (err) {
      error = err instanceof Error ? err.message : "Login failed";
    } finally {
      loading = false;
    }
  }
</script>

<div class="grid min-h-screen lg:grid-cols-2">
  <!-- Left panel — literary brand -->
  <div class="relative hidden flex-col justify-between bg-foreground p-12 text-background lg:flex">
    <div class="absolute inset-0 opacity-[0.03]"
      style="background-image: url(&quot;data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E&quot;); background-size: 200px 200px;">
    </div>

    <div class="relative">
      <span class="font-serif text-xl font-semibold tracking-tight text-amber-400/90">Scriptorium</span>
    </div>

    <div class="relative space-y-6">
      <div class="h-px w-12 bg-amber-400/60"></div>
      <blockquote class="font-serif text-2xl font-medium leading-relaxed text-background/90 italic">
        "Turning a collection into a library."
      </blockquote>
      <p class="text-sm text-background/40 not-italic">— Scriptorium</p>
    </div>

    <div class="relative text-xs text-background/25">
      Your personal library, self-hosted.
    </div>
  </div>

  <!-- Right panel — form -->
  <div class="flex flex-col items-center justify-center px-6 py-16 sm:px-12 lg:px-16">
    <div class="w-full max-w-sm">

      <!-- Mobile brand -->
      <div class="mb-8 text-center lg:hidden">
        <span class="font-serif text-2xl font-semibold tracking-tight">Scriptorium</span>
      </div>

      <!-- Header -->
      <div class="mb-8">
        <h1 class="font-serif text-3xl font-semibold tracking-tight text-foreground">
          Welcome back
        </h1>
        <p class="mt-2 text-sm text-muted-foreground">
          Sign in to continue to your library.
        </p>
      </div>

      {#if error}
        <div class="mb-6 rounded-md border border-destructive/30 bg-destructive/8 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      {/if}

      {#if oidcEnabled}
        <Button variant="outline" class="mb-6 w-full" href="/api/v1/auth/oidc/login">
          Sign in with SSO
        </Button>
        <div class="relative mb-6">
          <Separator />
          <span class="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-background px-2 text-xs text-muted-foreground">
            or continue with
          </span>
        </div>
      {/if}

      <form onsubmit={handleSubmit} class="space-y-5">
        <div class="space-y-1.5">
          <label for="username" class="text-sm font-medium text-foreground">Username</label>
          <Input
            id="username"
            bind:value={username}
            placeholder="Your username"
            autocomplete="username"
            required
            disabled={loading}
          />
        </div>

        <div class="space-y-1.5">
          <label for="password" class="text-sm font-medium text-foreground">Password</label>
          <Input
            id="password"
            type="password"
            bind:value={password}
            placeholder="Your password"
            autocomplete="current-password"
            required
            disabled={loading}
          />
        </div>

        <Button type="submit" class="w-full" disabled={loading}>
          {loading ? "Signing in…" : "Sign in"}
        </Button>
      </form>

      <p class="mt-8 text-center text-sm text-muted-foreground">
        Don't have an account?
        <a href="/auth/register" class="font-medium text-foreground underline-offset-4 hover:underline">
          Create one
        </a>
      </p>
    </div>
  </div>
</div>
