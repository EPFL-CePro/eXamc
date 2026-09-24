import { defineConfig } from 'vite';
import { resolve } from 'path';

export default defineConfig({
  base: '/static/vite',
  resolve: {
    alias: {
      '@examc': resolve(import.meta.dirname, 'src'),
    },
  },
  build: {
    outDir: resolve(import.meta.dirname, 'dist/vite'),
    manifest: "manifest.json",
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
        "amc/amc_results": resolve(import.meta.dirname, 'src/views/amc/amc_results/index.ts'),
        "impersonation/select_user": resolve(import.meta.dirname, 'src/views/impersonation/select_user/index.ts'),
        "res_and_stats/students_results": resolve(import.meta.dirname, 'src/views/res_and_stats/students_results/index.ts'),
        "review/review_group": resolve(import.meta.dirname, 'src/views/review/review_group/index.ts'),
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