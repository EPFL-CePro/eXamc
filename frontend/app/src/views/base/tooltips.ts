import { Tooltip } from "bootstrap";

const TOOLTIP_SELECTOR = '[data-bs-toggle="tooltip"], [data-bs-title]:not([data-bs-toggle="popover"])';
/** 
 * Initializes the tooltips in `root`, including `root` itself. Already initialized ones are left as they are.
 *
 **/
export function initTooltips(root: Element): void {
    const elements: Element[] = [...root.querySelectorAll(TOOLTIP_SELECTOR)];
    if (root.matches(TOOLTIP_SELECTOR)) elements.push(root);
    for (const element of elements) Tooltip.getOrCreateInstance(element);

    // Clicking focuses a button, and a tooltip stays open while its element has focus: close it on click.
    // It shows again on the next hover, or when the element is focused from the keyboard.
    document.addEventListener("click", (event) => {
        const element = (event.target as Element).closest(TOOLTIP_SELECTOR);
        if (element) Tooltip.getInstance(element)?.hide();
    });

    // A dropdown toggle's tooltip would cover its open menu
    document.addEventListener("show.bs.dropdown", (event) => Tooltip.getInstance(event.target as Element)?.hide());
}
