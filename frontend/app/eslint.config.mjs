import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";
import css from "@eslint/css";
import stylistic from "@stylistic/eslint-plugin";
import { defineConfig, globalIgnores } from "eslint/config";

const jsTs = ["**/*.{js,mjs,cjs,ts,mts,cts}"];

export default defineConfig([
  globalIgnores([
    "**/dist/**",
    "**/node_modules/**",
    "**/vite/**",
    "**/*.{js,mjs,cjs}",
    "src/styles/jquery-comments.css",
    "src/legacy/**",
  ]),
  {
    files: jsTs,
    extends: [js.configs.recommended, tseslint.configs.recommended],
        languageOptions: {
      globals: {
        ...globals.browser,
        CeleryProgressBar: "readonly", // loaded by celery-progress's script; typed in src/types/definitions/celery-progress.d.ts
      },
    },
    rules: {
      "no-undef": "error",
    },
  },
  {
    files: jsTs,
    plugins: { "@stylistic": stylistic },
    rules: {
      "@stylistic/member-delimiter-style": "error", // semicolons in interfaces/types
      "@stylistic/semi": ["error", "always"],
    },
  },
  {
    files: ["**/*.css"],
    plugins: { css },
    language: "css/css",
    extends: ["css/recommended"],
    rules: {
      "css/font-family-fallbacks": "off", // Off for FontAwesome
      "css/no-important": "off",
      "css/use-baseline": ["error", { allowProperties: ["user-select"] }],
    },
  },
]);
