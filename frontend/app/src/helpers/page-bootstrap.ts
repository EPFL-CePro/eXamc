import type { Modal } from "bootstrap";

/**
 * Bootstrap 5 of the page (legacy/bootstrap-cdn.html), not the npm package: importing it would load a second
 * Bootstrap in dev mode, whose data-api handlers toggle the dropdowns a second time (they never open).
 */
export function getPageBootstrap(): { Modal: typeof Modal } {
    return (window as unknown as { bootstrap: { Modal: typeof Modal } }).bootstrap;
}
