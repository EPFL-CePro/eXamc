/**
 * entries/core.ts
 * ---------------
 * Loaded on EVERY page via base.html:
 *   {% vite_asset 'entries/core.ts' %}
 *
 * Only what genuinely belongs on every page lives here: jQuery (because
 * every other entry below assumes it's already global), Bootstrap,
 * Font Awesome, and the site's own CSS. Page-specific plugins
 * (editor.ts, forms.ts, charts.ts) are separate entries — see each file's
 * header for which templates load it and why it's not here.
 */

// jQuery must go first and be pinned to `window` — every other entry's
// jQuery plugins assume a global `$` already exists when they execute.
import jQuery from 'jquery'
import 'jquery-ui/dist/jquery-ui.js'

declare global {
  interface Window {
    jQuery: typeof jQuery
    $: typeof jQuery
  }
}
window.jQuery = jQuery
window.$ = jQuery

// Font Awesome (CSS only).
import '@fortawesome/fontawesome-free/css/all.min.css'

// Site CSS.
import '../styles/menubars.css'
import '../styles/examc.css'

// Bootstrap 5 (JS + CSS)
import 'bootstrap/dist/js/bootstrap.bundle.min.js'
import 'bootstrap/dist/css/bootstrap.min.css'