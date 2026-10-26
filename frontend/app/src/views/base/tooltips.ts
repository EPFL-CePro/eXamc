import { Tooltip } from "bootstrap";

const TOOLTIP_SELECTOR = '[data-bs-toggle="tooltip"]';

/** 
 * Initializes the tooltips in `root`, including `root` itself. Already initialized ones are left as they are.
 *
 **/
export function initTooltips(root: Element): void {
    const elements: Element[] = [...root.querySelectorAll(TOOLTIP_SELECTOR)];
    if (root.matches(TOOLTIP_SELECTOR)) elements.push(root);
    for (const element of elements) Tooltip.getOrCreateInstance(element);    
}
