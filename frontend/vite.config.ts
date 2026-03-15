import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [tailwindcss(), sveltekit()],
  resolve: {
    conditions: ['svelte', 'browser', 'import', 'module', 'default'],
  },
  ssr: {
    resolve: {
      conditions: ['svelte'],
      externalConditions: ['svelte'],
    },
  },
  server: {
    hmr: { port: 5173 },
    proxy: {
      '/api': {
        target: process.env.VITE_BACKEND_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: process.env.VITE_BACKEND_URL || 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
    }
  }
});
