/**
 * entries/forms.ts
 * ----------------
 * Loaded ONLY by templates using the multi-select widget or AJAX
 * modal-form submission. Add to those specific templates, not base.html:
 *   {% block extra_head %}{% vite_asset 'entries/forms.ts' %}{% endblock %}
 *
 * Not in core.ts: both are jQuery plugins used on specific forms, not
 * every page — no reason to ship them everywhere.
 *
 * Assumes core.ts already ran (window.jQuery / window.$ set) — this entry
 * must be placed AFTER core.ts's <script> tag in the rendered HTML.
 */

// jQuery plugin: cross-list multi-select. Usage in templates:
//   $(".jquery-selector").multiselect()
// Source: https://github.com/crlcu/multiselect/ (last commit 2022, no npm
// package — see base.README.md for why this stays vendored).
import '../lib/legacy/multiselect.min.js'

// jQuery plugin (partial file): loads a form into a modal, submits via
// AJAX. Usage in templates:
//   $('#button').modalForm({ formURL: '/path/to/form/' })
// Source: https://github.com/trco/django-bootstrap-modal-forms — ships as
// a static file inside that PyPI package, not on npm.
import '../lib/legacy/jquery.bootstrap.modal.forms.min.js'