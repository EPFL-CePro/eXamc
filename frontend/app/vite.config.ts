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
        // Entries shared by multiple views
        "base": resolve(import.meta.dirname, 'src/views/base/index.ts'),

        // Entries used by single views
        "amc/amc": resolve(import.meta.dirname, 'src/views/amc/amc/index.ts'),
        "amc/_reports": resolve(import.meta.dirname, 'src/views/amc/_reports/index.ts'),
        "amc/_data_capture": resolve(import.meta.dirname, 'src/views/amc/_data_capture/index.ts'),
        "amc/_markings": resolve(import.meta.dirname, 'src/views/amc/_markings/index.ts'),
        "amc/_project": resolve(import.meta.dirname, 'src/views/amc/_project/index.ts'),
        
        "public/csvgen": resolve(import.meta.dirname, 'src/views/public/csvgen/index.ts'),
        "public/room_plan": resolve(import.meta.dirname, 'src/views/public/room_plan/index.ts'),

        "errors/_user_facing_error_modal": resolve(import.meta.dirname, 'src/views/errors/_user_facing_error_modal/index.ts'),

        "exam/exam_info": resolve(import.meta.dirname, 'src/views/exam/exam_info/index.ts'),
        "exam/preparation/exam_preparation": resolve(import.meta.dirname, 'src/views/exam/preparation/exam_preparation/index.ts'),
        "exam/preparation/exam_preparation_students": resolve(import.meta.dirname, 'src/views/exam/preparation/exam_preparation_students/index.ts'),
        
        "home": resolve(import.meta.dirname, 'src/views/home/index.ts'),

        "impersonation/select_user": resolve(import.meta.dirname, 'src/views/impersonation/select_user/index.ts'),
        
        "import/import": resolve(import.meta.dirname, 'src/views/import/import/index.ts'),
        "import/_import_types/review": resolve(import.meta.dirname, 'src/views/import/_import_types/review/index.ts'),
        "import/_import_types/amc": resolve(import.meta.dirname, 'src/views/import/_import_types/amc/index.ts'),

        "res_and_stats/students_results": resolve(import.meta.dirname, 'src/views/res_and_stats/students_results/index.ts'),
        "res_and_stats/general_statistics": resolve(import.meta.dirname, 'src/views/res_and_stats/general_statistics/index.ts'),
        "res_and_stats/questions_statistics": resolve(import.meta.dirname, 'src/views/res_and_stats/questions_statistics/index.ts'),
        
        "review/review_group": resolve(import.meta.dirname, 'src/views/review/review_group/index.ts'),
        "review/settings/review_settings": resolve(import.meta.dirname, 'src/views/review/settings/review_settings/index.ts'),
        "review/settings/_manage_exam_pages_groups": resolve(import.meta.dirname, 'src/views/review/settings/_manage_exam_pages_groups/index.ts'),
        "review/_review_grading_scheme_panel": resolve(import.meta.dirname, 'src/views/review/_review_grading_scheme_panel/index.ts'),
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
