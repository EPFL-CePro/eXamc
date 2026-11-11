import { Popover } from 'bootstrap';

/** The parts of the viewer's markup used by the element. */
export interface ViewerParts {
    stage: HTMLDivElement;
    message: HTMLElement;
    pageIndicator: HTMLElement;
}

/** Frosted glass behind the toolbars: the page shows through, blurred. */
const FROSTED = 'background: #ffffffa3; backdrop-filter: blur(5px); -webkit-backdrop-filter: blur(5px);';

const TEMPLATE = `
    <div data-part="stage" class="position-absolute top-0 start-0 w-100 h-100"></div>
    <div data-part="secondary" class="position-absolute top-0 start-0 m-2 z-1 d-flex align-items-start gap-1"></div>
    <div class="btn-group-vertical position-absolute top-0 end-0 m-2 z-1 rounded shadow-sm" style="${FROSTED}"
         role="toolbar" aria-label="Page view">
        <button type="button" class="btn btn-outline-dark" data-command="zoom-in" aria-label="Zoom in" title="Zoom in (+)">
            <i class="fa-solid fa-magnifying-glass-plus" aria-hidden="true"></i>
        </button>
        <button type="button" class="btn btn-outline-dark" data-command="zoom-out" aria-label="Zoom out" title="Zoom out (−)">
            <i class="fa-solid fa-magnifying-glass-minus" aria-hidden="true"></i>
        </button>
        <button type="button" class="btn btn-outline-dark" data-command="fit" aria-label="Fit" title="Fit (0)">
            <i class="fa-solid fa-arrows-to-dot" aria-hidden="true"></i>
        </button>
        <button type="button" class="btn btn-outline-dark" data-part="help" aria-label="How to navigate"
                data-bs-toggle="popover" data-bs-placement="left" data-bs-trigger="hover focus" data-bs-html="true">
            <i class="fa-regular fa-circle-question" aria-hidden="true"></i>
        </button>
    </div>
    <div data-part="page-indicator" hidden aria-live="polite"
         class="position-absolute bottom-0 start-50 translate-middle-x mb-2 z-1 px-2 py-1 rounded shadow-sm small pe-none"
         style="${FROSTED}"></div>
    <div data-part="message" hidden
         class="position-absolute top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center
                text-center text-body-secondary p-3 pe-none"></div>
`;

/** Help lines; Bootstrap's popover sanitizer only keeps basic tags (no <kbd>). */
const HELP = `
    <li><b>Drag</b> to move the pages</li>
    <li><b>Wheel</b>: scroll</li>
    <li><b>Ctrl/Cmd + wheel</b> or <b>+ / −</b> to zoom</li>
    <li><b>0</b> or double-click: fit</li>
    <li><b>Page Up / Down</b>, <b>Home / End</b>: other pages</li>
    <li><b>Shift + arrows</b> to move the pages</li>
`;

/**
 * Builds the viewer's markup in its element. The page's children are kept by their `slot` attribute:
 * `toolbar` goes to the secondary toolbar (top left), `help` (`<li>`) to the help popover.
 *
 * @param {HTMLElement} host - The viewer element.
 * @return {ViewerParts} The parts the element uses.
 */
export function render(host: HTMLElement): ViewerParts {
    const given = [...host.children];
    host.innerHTML = TEMPLATE;
    const part = (name: string): HTMLElement => host.querySelector<HTMLElement>(`[data-part="${name}"]`)!;

    let helpLines = HELP;
    for (const child of given) {
        const slot = child.getAttribute('slot');
        if (slot === 'toolbar') part('secondary').append(child);
        else if (slot === 'help') helpLines += child.outerHTML;
    }

    // Configured by its data-bs-* attributes; Bootstrap doesn't start popovers by itself
    const helpButton = part('help');
    helpButton.dataset['bsContent'] = `<ul class="list-unstyled small lh-lg mb-0">${helpLines}</ul>`;
    Popover.getOrCreateInstance(helpButton);

    return { stage: part('stage') as HTMLDivElement, message: part('message'), pageIndicator: part('page-indicator') };
}