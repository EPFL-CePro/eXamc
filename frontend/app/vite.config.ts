import { defineConfig } from 'vite';
import { resolve } from 'path';


export default defineConfig({
  base: '/static/vite',
  build: {
    outDir: resolve(import.meta.dirname, 'dist/vite'),
    manifest: false,
    rollupOptions: {
      input: {
        // Entries used by multiple views
        "charts": resolve(import.meta.dirname, 'src/entries/charts.ts'),
        "core": resolve(import.meta.dirname, 'src/entries/core.ts'),
        "editor": resolve(import.meta.dirname, 'src/entries/editor.ts'),
        "forms": resolve(import.meta.dirname, 'src/entries/forms.ts'),
        "pdf-utils": resolve(import.meta.dirname, 'src/entries/pdfUtils.ts'),

        // Entries used by single views
        "home": resolve(import.meta.dirname, 'src/views/home/index.ts'),
      },
      output: {
        entryFileNames: "[name].js",
        assetFileNames: "[name][extname]",
      },
    },
  },
  server: {
    // Django serves pages on :8000, Vite serves assets on :5173.
    // Without this, Vite's dev server generates asset URLs relative to
    // whatever origin loaded the page (Django's), not its own — so the
    // browser tries to fetch HMR/JS/CSS from :8000 and gets 404s from Django.
    // This forces Vite to always point back at itself.
    origin: 'http://localhost:5173',
  },
});