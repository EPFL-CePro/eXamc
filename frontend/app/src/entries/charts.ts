/**
 * entries/charts.ts
 * -----------------
 * Loaded only by the two templates that actually chart exam statistics:
 *   templates/res_and_stats/general_statistics.html
 *   templates/res_and_stats/questions_statistics.html
 *
 * Add to each:
 *   {% load django_vite %}
 *   {% vite_asset 'entries/charts.ts' %}
 *
 * Not in base.ts: only 2 templates need this — see base.README.md section 6.
 *
 * Chart.js: swapped from the vendored examc_app/static/js/Chart.min.js to
 * the real `chart.js` npm package (latest — no attempt made to match
 * whatever old version was vendored; going forward with current
 * dependencies across the board per project decision). Chart.js v4+
 * requires explicit component registration — Chart.js is modular now, so
 * only the pieces actually used get bundled. Import what your chart
 * configs actually use; the set below covers common bar/line/radar
 * dataset + scale + legend/tooltip usage. Expand if a template's
 * `new Chart(...)` call uses a chart type or plugin not registered here
 * (you'll get a clear runtime error naming the missing component if so).
 */
import {
  Chart,
  BarController,
  LineController,
  RadarController,
  PieController,
  DoughnutController,
  CategoryScale,
  LinearScale,
  RadialLinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Legend,
  Tooltip,
  Title,
} from 'chart.js'

Chart.register(
  BarController,
  LineController,
  RadarController,
  PieController,
  DoughnutController,
  CategoryScale,
  LinearScale,
  RadialLinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Legend,
  Tooltip,
  Title,
)

// Interop: both templates' inline <script> blocks call `new Chart(ctx, {...})`
// as a bare global today, not a module import. Keep this until those
// blocks are migrated to real modules.
declare global {
  interface Window {
    Chart: typeof Chart
  }
}
window.Chart = Chart

import '../legacy/palette.min.js'