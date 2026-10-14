import type { Collapse, Dropdown, Modal, Tab } from "bootstrap";

type PageBootstrap = { 
    Collapse: typeof Collapse; 
    Dropdown: typeof Dropdown; 
    Modal: typeof Modal;
    Tab: typeof Tab;
 };

/**
 * Bootstrap 5 of the page (legacy/bootstrap-cdn.html), not the npm package: importing the package bundles a
 * second Bootstrap whose data-api handlers toggle the dropdowns a second time, so they never open.
 */
export function getPageBootstrap(): PageBootstrap {
    return (window as unknown as { bootstrap: PageBootstrap }).bootstrap;
}
