import { Tab } from "bootstrap";

const TAB_PARAM = "tab";

/**
 * Shows the tab from the `?tab=` query parameter, else the one selected by the server, else the default tab.
 * Only enabled tabs of this page are considered, so a hand-written parameter can't select anything else.
 */
export function manageTabs(options?: { tabs?: HTMLButtonElement[]; tabListSelector?: string; tabId?: string }): void {
    const { tabId, tabListSelector = ".nav-pills" } = options || {};
    let { tabs = [] } = options || {};

    // find tabs if none were given
    if (tabs.length === 0) tabs = [...document.querySelectorAll<HTMLButtonElement>(`${tabListSelector} [data-bs-toggle="pill"]`)];

    // Keep the selected tab in the URL without adding history entries or reloading.
    // Other query parameters and any hash are preserved.
    for (const tab of tabs) {
        tab.addEventListener("shown.bs.tab", () => {
            const url = new URL(window.location.href);
            url.searchParams.set(TAB_PARAM, tab.id);
            history.replaceState(history.state, "", url);
        });
    }

    const candidateIds: string[] = [];
    const fromUrl = new URLSearchParams(window.location.search).get(TAB_PARAM);
    if (fromUrl) candidateIds.push(fromUrl);
    if (tabId) candidateIds.push(tabId);

    const tab = candidateIds
        .map((id) => tabs.find((button) => button.id === id && !button.disabled))
        .find((button) => button !== undefined) ?? tabs[0];

    if (tab) Tab.getOrCreateInstance(tab).show();
}