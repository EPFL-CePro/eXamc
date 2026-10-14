import { getPageBootstrap } from "@examc/helpers/page-bootstrap";

/** Tab shown when neither the URL hash nor the server selects one. */
const DEFAULT_TAB_ID = 'project-tab';

/**
 * Shows the tab from the URL hash, else the one selected by the server, else the default tab.
 * Only enabled tabs of this page are considered, so a hand-written hash can't select anything else.
 *
 * @param {HTMLAnchorElement[]} tabs - The tab links of the page.
 * @param {string} serverTabId - The tab id selected by the server ('' if none).
 */
export function showInitialTab(tabs: HTMLAnchorElement[], serverTabId: string): void {
    const candidateIds = [window.location.hash.slice(1), serverTabId.replace(/^#/, ''), DEFAULT_TAB_ID];
    const tab = candidateIds
        .map((id) => tabs.find((link) => link.id === id && !link.classList.contains('disabled')))
        .find((link) => link !== undefined) ?? tabs[0];

    if (tab) getPageBootstrap().Tab.getOrCreateInstance(tab).show();
}