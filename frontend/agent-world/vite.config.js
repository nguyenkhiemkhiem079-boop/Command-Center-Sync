import { resolve } from 'node:path';
import { defineConfig } from 'vite';

export default defineConfig({
  configFile: false,
  build: {
    target: 'es2022',
    minify: 'oxc',
    sourcemap: false,
    emptyOutDir: false,
    lib: {
      entry: resolve(import.meta.dirname, 'src/main.js'),
      formats: ['es'],
      fileName: () => 'agent-world.js',
    },
    rollupOptions: {
      output: {
        format: 'es',
        entryFileNames: 'agent-world.js',
        chunkFileNames: 'chunk-[hash].js',
        assetFileNames: 'asset-[hash][extname]',
      },
    },
    outDir: resolve(import.meta.dirname, '../../web/agent-world'),
  },
});
