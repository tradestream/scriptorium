<script lang="ts">
  import { goto } from "$app/navigation";
  import { setAuthToken } from "$lib/api/client";
  import * as api from "$lib/api/client";
  import { Button } from "$lib/components/ui/button";
  import { Input } from "$lib/components/ui/input";
  import type { RegisterRequest } from "$lib/types/index";

  let username = $state("");
  let email = $state("");
  let password = $state("");
  let passwordConfirm = $state("");
  let error = $state("");
  let loading = $state(false);

  async function handleSubmit(e: SubmitEvent) {
    e.preventDefault();
    error = "";

    if (password !== passwordConfirm) {
      error = "Passwords do not match";
      return;
    }

    loading = true;

    try {
      const data: RegisterRequest = { username, email, password };
      const result = await api.register(data);
      if (result.access_token) {
        setAuthToken(result.access_token);
        await goto("/");
      }
    } catch (err) {
      error = err instanceof Error ? err.message : "Registration failed";
    } finally {
      loading = false;
    }
  }
</script>

<div class="grid min-h-screen lg:grid-cols-2">
  <!-- Left panel — literary brand -->
  <div class="relative hidden flex-col justify-between bg-foreground p-12 text-background lg:flex">
    <!-- Decorative grain overlay -->
    <div class="absolute inset-0 opacity-[0.03]"
      style="background-image: url(&quot;data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E&quot;); background-size: 200px 200px;">
    </div>

    <div class="relative">
      <span class="font-serif text-xl font-semibold tracking-tight text-amber-400/90">Scriptorium</span>
    </div>

    <div class="relative space-y-6">
      <div class="h-px w-12 bg-amber-400/60"></div>
      <blockquote class="font-serif text-2xl font-medium leading-relaxed text-background/90 italic">
        "A reader lives a thousand lives before he dies. The man who never reads lives only one."
      </blockquote>
      <p class="text-sm text-background/40 not-italic">— George R.R. Martin</p>
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
          Create your account
        </h1>
        <p class="mt-2 text-sm text-muted-foreground">
          The first account becomes the administrator.
        </p>
      </div>

      {#if error}
        <div class="mb-6 rounded-md border border-destructive/30 bg-destructive/8 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      {/if}

      <form onsubmit={handleSubmit} class="space-y-5">
        <div class="space-y-1.5">
          <label for="username" class="text-sm font-medium text-foreground">Username</label>
          <Input
            id="username"
            bind:value={username}
            placeholder="hemingway"
            autocomplete="username"
            required
            disabled={loading}
          />
        </div>

        <div class="space-y-1.5">
          <label for="email" class="text-sm font-medium text-foreground">Email</label>
          <Input
            id="email"
            type="email"
            bind:value={email}
            placeholder="you@example.com"
            autocomplete="email"
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
            placeholder="At least 8 characters"
            autocomplete="new-password"
            required
            disabled={loading}
          />
        </div>

        <div class="space-y-1.5">
          <label for="password-confirm" class="text-sm font-medium text-foreground">Confirm password</label>
          <Input
            id="password-confirm"
            type="password"
            bind:value={passwordConfirm}
            placeholder="Repeat your password"
            autocomplete="new-password"
            required
            disabled={loading}
          />
        </div>

        <Button type="submit" class="w-full" disabled={loading}>
          {loading ? "Creating account…" : "Create account"}
        </Button>
      </form>

      <p class="mt-8 text-center text-sm text-muted-foreground">
        Already have an account?
        <a href="/auth/login" class="font-medium text-foreground underline-offset-4 hover:underline">
          Sign in
        </a>
      </p>
    </div>
  </div>
</div>
