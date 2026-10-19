const STORAGE_KEY = 'examc:exam-info:open-sections';

/** Sections open the first time the page is visited. */
const DEFAULT_OPEN = ['section-exam'];

function loadOpenSections(): Set<string> {
    try {
        const saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY) ?? 'null') as unknown;
        if (Array.isArray(saved)) return new Set(saved.filter((id): id is string => typeof id === 'string'));
    } catch {
        // Storage unavailable or corrupted: the defaults are used.
    }
    return new Set(DEFAULT_OPEN);
}

function saveOpenSections(open: Set<string>): void {
    try {
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify([...open]));
    } catch {
        // Storage unavailable: the sections just aren't remembered.
    }
}

/**
 * Reopens the sections that were open before the page reloaded (every save reloads it),
 * and remembers the ones the user opens or closes.
 *
 * @param {HTMLElement} accordion - The accordion.
 */
export function initAccordion(accordion: HTMLElement): void {
    const open = loadOpenSections();

    for (const section of accordion.querySelectorAll<HTMLElement>('.accordion-collapse')) {
        if (open.has(section.id)) {
            // Shown directly, without the opening animation
            section.classList.add('show');
            const button = accordion.querySelector(`[data-bs-target="#${CSS.escape(section.id)}"]`);
            button?.classList.remove('collapsed');
            button?.setAttribute('aria-expanded', 'true');
        }

        section.addEventListener('shown.bs.collapse', () => {
            open.add(section.id);
            saveOpenSections(open);
        });
        section.addEventListener('hidden.bs.collapse', () => {
            open.delete(section.id);
            saveOpenSections(open);
        });
    }
}