import { Tab } from "bootstrap";

/** Tab shown when neither the URL hash nor the server selects one. */
const DEFAULT_TAB_ID = 'project-tab';

/**
 * Shows the tab from the URL hash, else the one selected by the server, else the default tab.
 * Only enabled tabs of this page are considered, so a hand-written hash can't select anything else.
 *
 * @param {HTMLButtonElement[]} tabs - The tab buttons of the page.
 * @param {string} serverTabId - The tab id selected by the server ('' if none).
 */
export function showInitialTab(tabs: HTMLButtonElement[], serverTabId: string): void {
    const candidateIds = [window.location.hash.slice(1), serverTabId.replace(/^#/, ''), DEFAULT_TAB_ID];
    const tab = candidateIds
        .map((id) => tabs.find((button) => button.id === id && !button.disabled))
        .find((button) => button !== undefined) ?? tabs[0];

    if (tab) Tab.getOrCreateInstance(tab).show();
}