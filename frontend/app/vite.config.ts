import { defineConfig } from 'vite';
import { resolve } from 'path';
import checker from 'vite-plugin-checker';

export default defineConfig({
  base: '/static/vite',
  resolve: {
    alias: {
      '@examc': resolve(import.meta.dirname, 'src'),
    },
  },
  plugins: [
    checker({
      typescript: true,
      eslint: { lintCommand: 'eslint .', useFlatConfig: true },
    }),
  ],
  build: {
    outDir: resolve(import.meta.dirname, 'dist/vite'),
    manifest: "manifest.json",
    rolldownOptions: {
      input: {
        // Shared entries used by multiple views
        "examc": resolve(import.meta.dirname, 'src/styles/examc.scss'),

        // Entries used by single views
        "home": resolve(import.meta.dirname, 'src/views/home/index.ts'),
        "amc/amc_results": resolve(import.meta.dirname, 'src/views/amc/amc_results/index.ts'),
        "amc/amc_data_capture_manual": resolve(import.meta.dirname, 'src/views/amc/amc_data_capture_manual/index.ts'),
        "amc/amc_data_capture": resolve(import.meta.dirname, 'src/views/amc/amc_data_capture/index.ts'),
        "csvgen/csvgen": resolve(import.meta.dirname, 'src/views/csvgen/csvgen/index.ts'),
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