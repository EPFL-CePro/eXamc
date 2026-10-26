import { Tab } from "bootstrap";

const TAB_PARAM = "tab";

/**
 * Keeps the `?tab=` query parameter in sync with the selected tab.
 * The initial tab is selected by the server; `tabId` (a button id) overrides it if given.
 * Only enabled tabs of this page are considered.
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
            url.searchParams.set(TAB_PARAM, tab.dataset.tabKey ?? tab.id);
            history.replaceState(history.state, "", url);
        });
    }

    // Explicit override only; otherwise trust the server-rendered state.
    if (tabId) {
        const tab = tabs.find((button) => button.id === tabId && !button.disabled);
        if (tab) Tab.getOrCreateInstance(tab).show();
    }
}