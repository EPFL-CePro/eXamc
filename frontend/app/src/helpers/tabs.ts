import { Tab } from "bootstrap";

const BASE_TAB_KEY = "tab";
const BASE_TAB_SELECTOR = ".nav-pills";

interface SingleTabOptions {
    /** Query selectors of the parent elements of the pill elements. Must not contain `.nav-pills`. */
    tabListSelectors: string[];

    /** The key to use in the URL. Must not be `tab`. */
    tabKey: string;
}

interface ManageTabsOptions {
    tabListSelector?: string;
    additionalTabs?: SingleTabOptions[];
}

/** The key a tab is saved under in the URL. */
function keyOf(tab: HTMLButtonElement): string {
    return tab.dataset.tabKey ?? tab.id;
}
/**
 * Keeps `?<urlKey>=` in sync with the selected tab of these lists, and keeps the lists in sync with each other:
 * selecting a tab in one list selects the tab with the same key in the others.
 * `selectFromUrl`: also select, on load, the tab the URL names (the server only does it for `?tab=`).
 */
function initTabs(tabs: HTMLButtonElement[], urlKey: string, selectFromUrl: boolean): void {
    /** Set while the other lists are being updated, so their `shown` events don't start another round. */
    let syncing = false;

    const selectEverywhere = (key: string): void => {
        syncing = true;
        
        try {
            for (const tab of tabs) {
                if (keyOf(tab) === key && !tab.disabled && !tab.classList.contains("active")) {
                    Tab.getOrCreateInstance(tab).show();
                }
            }
        } finally {
            syncing = false;
        }
    };

    for (const tab of tabs) {
        Tab.getOrCreateInstance(tab);

        tab.addEventListener("shown.bs.tab", () => {
            if (syncing) return;

            // Keep the selected tab in the URL without adding history entries or reloading.
            // Other query parameters and any hash are preserved.
            const url = new URL(window.location.href);
            url.searchParams.set(urlKey, keyOf(tab));
            history.replaceState(history.state, "", url);

            selectEverywhere(keyOf(tab));
        });
    }

    if (!selectFromUrl) return;

    const wanted = new URL(window.location.href).searchParams.get(urlKey);
    if (wanted) selectEverywhere(wanted);
}

/**
 * Keeps the selected tabs in the URL: `?tab=` for the page's tabs, and each additional group's own key.
 * The page's initial tab is selected by the server; additional groups are selected here from their key.
 */
export function manageTabs(options?: ManageTabsOptions): void {
    const { tabListSelector = BASE_TAB_SELECTOR, additionalTabs = [] } = options || {};

    const findTabs = (selectors: string[]): HTMLButtonElement[] =>
        selectors.flatMap((selector) => [
            ...document.querySelectorAll<HTMLButtonElement>(`${selector} [data-bs-toggle="pill"]`),
        ]);

    const validGroups = additionalTabs.filter((group) => {
        if (group.tabListSelectors.includes(BASE_TAB_SELECTOR) || group.tabKey === BASE_TAB_KEY) {
            console.error(
                `Tabs: an additional group can't use the '${BASE_TAB_KEY}' key or the '${BASE_TAB_SELECTOR}' selector.`,
                group,
            );
            return false;
        }
        return true;
    });

    // Tabs of an additional group are only managed by that group, never under `?tab=`
    const additionalSelectors = validGroups.flatMap((group) => group.tabListSelectors);
    const baseTabs = findTabs([tabListSelector]).filter(
        (tab) => !additionalSelectors.some((selector) => tab.closest(selector)),
    );

    initTabs(baseTabs, BASE_TAB_KEY, false);
    validGroups.forEach((group) => initTabs(findTabs(group.tabListSelectors), group.tabKey, true));
}