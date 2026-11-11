import { HttpProgressBar } from '@examc/helpers/http.ts';

/**
 * Controls a button's busy state: disabled, with a spinner and a label, or back to its content.
 *
 * @param {HTMLButtonElement} button - The button.
 * @return {(label: string | null) => void} Sets the busy label (a constant of ours, set as HTML), or null when done.
 */
export function busyButton(button: HTMLButtonElement): (label: string | null) => void {
    const content = button.innerHTML;
    return (label) => {
        const busy = label !== null;
        button.disabled = busy;
        button.setAttribute('aria-busy', String(busy));
        button.innerHTML = busy
            ? `<span class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span> ${label}`
            : content;
    };
}

/**
 * A progress bar placed right after an element, hidden until shown (as on the import page).
 *
 * @param {Element} anchor - The element it goes after.
 * @param {string} label - Accessible name of the bar.
 * @return {HttpProgressBar} The bar.
 */
export function progressAfter(anchor: Element, label: string): HttpProgressBar {
    const progress = HttpProgressBar.create(label);
    progress.element.classList.add('mt-3');
    anchor.after(progress.element);
    return progress;
}