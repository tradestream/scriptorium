import adapterNode from '@sveltejs/adapter-node';
import adapterStatic from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

const isCapacitor = process.env.BUILD_TARGET === 'capacitor';

export default {
  preprocess: vitePreprocess(),
  kit: {
    adapter: isCapacitor
      ? adapterStatic({
          pages: 'build',
          assets: 'build',
          fallback: 'index.html',
          precompress: false,
        })
      : adapterNode(),
    alias: {
      $lib: 'src/lib'
    }
  }
};
