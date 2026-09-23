/**
 * entries/core.ts
 * ---------------
 * Loaded on EVERY page via base.html:
 *   {% vite_asset 'entries/core.ts' %}
 *
 * Only what genuinely belongs on every page lives here: Bootstrap,
 * Font Awesome, and the site's own CSS. Page-specific plugins
 * (editor.ts, forms.ts, charts.ts) are separate entries — see each file's
 * header for which templates load it and why it's not here.
 */

// Font Awesome (CSS only).
import '@fortawesome/fontawesome-free/css/all.min.css';

// Site CSS.
import '../styles/menubars.scss';
import '../styles/examc.scss';

import '../legacy/jquery.bootstrap.modal.forms.min.js';

// Bootstrap 4.3.1
import '../legacy/bootstrap.min.css';

// TODO replace with up-to-date Bootstrap
// import 'bootstrap/dist/js/bootstrap.bundle.min.js';
// import 'bootstrap/dist/css/bootstrap.min.css';