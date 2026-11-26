/** An element the page must contain; fails loudly if the template and the script disagree. */
export function byId<T extends HTMLElement = HTMLElement>(id: string): T {
    const element = document.getElementById(id);
    if (!element) throw new Error(`#${id} is missing from the page`);
    return element as T;
}

/**
 * Whether a key event comes from someone typing: in a field of the page, or in a text marker's
 * editor (a <textarea> inside marker.js's shadow DOM, which the event's target alone doesn't reveal).
 */
export function isTyping(event: Event): boolean {
    const origin = event.composedPath()[0];
    if (!(origin instanceof Element)) return false;
    return origin.matches('input, textarea, select, [contenteditable="true"]');
}
