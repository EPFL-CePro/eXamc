// Remembered per browser: the panel left open is shown again on the next visit
const STORAGE_KEY = "examc.prepStudents.panel";

function storedPanel(): string | null {
    try {
        return window.localStorage.getItem(STORAGE_KEY);
    } catch {
        return null;
    }
}

function storePanel(name: string | null): void {
    try {
        if (name) window.localStorage.setItem(STORAGE_KEY, name);
        else window.localStorage.removeItem(STORAGE_KEY);
    } catch {
        // Storage blocked (private window...): the panel is just not remembered
    }
}

/**
 * Pills of the students page (nav-link with data-panel="<name>"): each opens the panel with the same data-panel
 * below them, at most one at a time; clicking the pill of the open panel, or the × of the panel, closes it.
 * Returns `openPanel`, e.g. to show the import panel when the exam has no students.
 */
export function initStudentsPanels(toolbar: HTMLElement): { openPanel: (name: string | null) => void; hasStoredPanel: boolean } {
    const pills = [...toolbar.querySelectorAll<HTMLAnchorElement>("a.nav-link[data-panel]")];
    const panels = [...document.querySelectorAll<HTMLElement>("section.prep-students-panel[data-panel]")];

    function openPanel(name: string | null): void {
        for (const panel of panels) {
            panel.hidden = panel.dataset.panel !== name;
        }
        for (const pill of pills) {
            const open = pill.dataset.panel === name;
            pill.setAttribute("aria-expanded", String(open));
            pill.classList.toggle("active", open);
        }
        storePanel(name);
    }

    for (const pill of pills) {
        pill.addEventListener("click", (event) => {
            // Not a navigation to #studentsPanel...
            event.preventDefault();
            const open = pill.getAttribute("aria-expanded") === "true";
            openPanel(open ? null : pill.dataset.panel ?? null);
        });
    }
    for (const panel of panels) {
        panel.querySelector(".prep-students-panel-close")?.addEventListener("click", () => {
            openPanel(null);
            toolbar.querySelector<HTMLAnchorElement>(`a.nav-link[data-panel="${panel.dataset.panel}"]`)?.focus();
        });
    }

    const stored = storedPanel();
    const hasStoredPanel = stored !== null && panels.some((panel) => panel.dataset.panel === stored);
    if (hasStoredPanel) openPanel(stored);

    return { openPanel, hasStoredPanel };
}
