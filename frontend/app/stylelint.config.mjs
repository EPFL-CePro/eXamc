/** @type {import("stylelint").Config} */
export default {
  extends: ["stylelint-config-standard-scss"],
  rules: {
    "font-family-no-missing-generic-family-keyword": [
      true,
      {
        "ignoreFontFamilies": ["FontAwesome"]
      }
    ]
  },
  ignoreFiles: [
    "**/dist/**",
    "**/node_modules/**",
    "**/vite/**",
    "**/*.{js,mjs,cjs}",
    "src/styles/jquery-comments.css",
    "src/legacy/**",
  ]
};
