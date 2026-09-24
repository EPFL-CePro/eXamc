/**
 * entries/editor.ts
 * -----------------
 * Loaded ONLY by templates that use the Summernote WYSIWYG editor with
 * LaTeX support (question text editing, grading scheme descriptions,
 * wherever Summernote + math shows up). Add to those specific templates,
 * not base.html:
 *   {% block extra_head %}{% vite_asset 'entries/editor.ts' %}{% endblock %}
 *
 * Not in core.ts: KaTeX + Summernote are heavy and only needed on a
 * handful of editing pages — no reason to ship them to every visitor.
 *
 * Assumes core.ts already ran (window.jQuery / window.$ set) — this entry
 * must be placed AFTER core.ts's <script> tag in the rendered HTML, or
 * Summernote's own <script> (loaded separately, see base.README.md) plus
 * summernote-math.js will throw on a missing `$`.
 */

// KaTeX — summernote-math renders LaTeX via window.katex.
import katex from 'katex'
declare global {
  interface Window {
    katex: typeof katex
  }
}
window.katex = katex
import 'katex/dist/katex.min.css'

// Summernote-math plugin (jQuery plugin, source:
// https://github.com/tylerecouture/summernote-math — no npm package
// exists for this. Requires window.katex above and window.$ from core.ts to already be set.
//import '../legacy/summernote-math.js'