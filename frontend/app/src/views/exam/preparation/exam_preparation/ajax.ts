import { LoadingModal, LocalModal } from "@examc/modals";

import { withSavingOverlay } from "./saving-overlay.ts";

export function getElement<T extends HTMLElement = HTMLElement>(selector: string): T | null {
    return document.querySelector<T>(selector);
}

export function showModal(selector: string): void {
    const element = getElement(selector);
    if (element) new LocalModal(element).show();
}

export function hideModal(selector: string): void {
    const element = getElement(selector);
    if (element) new LocalModal(element).hide();
}

/**
 * What shows that a request is running: the loading spinner (true), the saving overlay of the page ("saving": shown
 * above any open dialog, for the requests that rewrite the LaTeX files), or nothing (false, when the dialog shows its
 * own progress).
 */
export type Spinner = boolean | "saving";

/** Runs a request behind the chosen spinner. */
export function withSpinner<T>(spinner: Spinner, task: () => Promise<T>): Promise<T> {
    if (spinner === "saving") return withSavingOverlay(task);
    if (spinner) return new LoadingModal(task).result;
    return task();
}

/** Adds the parameters to the query string of a URL. */
export function withQuery(url: string, params: Record<string, string | number> = {}): string {
    const query = new URLSearchParams(Object.entries(params).map(([key, value]) => [key, String(value)])).toString();
    if (!query) return url;
    return `${url}${url.includes("?") ? "&" : "?"}${query}`;
}

/** Makes htmx set up the hx-* attributes of HTML inserted by a script (htmx only does it for its own swaps). */
export function processHtmx(element: Element): void {
    if (typeof htmx !== "undefined") htmx.process(element);
}

/** Shows an element hidden by an inline `display: none`. */
export function showElement(selector: string): void {
    const element = getElement(selector);
    if (element) element.style.display = "";
}

export function hideElement(selector: string): void {
    const element = getElement(selector);
    if (element) element.style.display = "none";
}

export function toggleElement(selector: string, visible: boolean): void {
    if (visible) showElement(selector);
    else hideElement(selector);
}
