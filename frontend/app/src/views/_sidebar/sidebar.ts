const STORAGE_KEY = 'examc:sidebar:collapsed';

function loadCollapsed(): boolean {
    try {
        return localStorage.getItem(STORAGE_KEY) === 'true';
    } catch {
        return false; // storage unavailable: expanded by default
    }
}

function saveCollapsed(collapsed: boolean): void {
    try {
        localStorage.setItem(STORAGE_KEY, String(collapsed));
    } catch {
        // Storage unavailable: the state just isn't remembered.
    }
}

/**
 * Makes the sidebar collapsible: collapsed, it only shows the icons and the small logo.
 * The labels stay readable by screen readers (visually-hidden), and the state is remembered.
 *
 * @param {HTMLElement} container - The sidebar.
 */
export function initSidebar(container: HTMLElement): void {
    const toggle = container.querySelector<HTMLButtonElement>('[data-sidebar-toggle]');
    const toggleIcon = toggle?.querySelector<HTMLElement>('[data-sidebar-toggle-icon]');
    const toggleLabel = toggle?.querySelector<HTMLElement>('[data-sidebar-label]');

    const apply = (collapsed: boolean): void => {
        for (const label of container.querySelectorAll('[data-sidebar-label]')) {
            label.classList.toggle('visually-hidden', collapsed);
        }
        for (const element of container.querySelectorAll('[data-sidebar-expanded]')) {
            element.classList.toggle('d-none', collapsed);
        }
        for (const element of container.querySelectorAll('[data-sidebar-collapsed]')) {
            element.classList.toggle('d-none', !collapsed);
        }

        if (toggle) {
            toggle.setAttribute('aria-expanded', String(!collapsed));
            toggle.title = collapsed ? 'Expand' : '';
        }
        if (toggleLabel) toggleLabel.textContent = collapsed ? 'Expand' : 'Collapse';
        toggleIcon?.classList.toggle('fa-angles-left', !collapsed);
        toggleIcon?.classList.toggle('fa-angles-right', collapsed);
    };

    let collapsed = loadCollapsed();
    apply(collapsed);

    toggle?.addEventListener('click', () => {
        collapsed = !collapsed;
        apply(collapsed);
        saveCollapsed(collapsed);
    });
}