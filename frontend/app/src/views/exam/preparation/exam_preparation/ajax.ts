import { LoadingModal, LocalModal } from "@examc/modals";

import { CSRF } from "./config.ts";

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

/** What the callbacks of a failed request get (the jqXHR of jQuery). */
export interface AjaxError {
    status: number;
    responseText: string;
    responseJSON?: unknown;
}

export interface AjaxCallbacks<T> {
    /** Show the loading spinner while the request runs (default), not when the dialog shows its own progress. */
    spinner?: boolean;
    success?: (data: T) => void;
    error?: (xhr: AjaxError) => void;
}

function ajaxRequest<T>(method: "GET" | "POST", url: string, data: object | string | undefined, callbacks: AjaxCallbacks<T> = {}) {
    const { spinner = true, success, error } = callbacks;

    // The spinner stays until the request is done (LoadingModal hides it when its task ends)
    let requestDone: () => void = () => undefined;
    if (spinner) void new LoadingModal(() => new Promise<void>((resolve) => { requestDone = resolve; })).result;

    return $.ajax({
        url,
        type: method,
        data: data ?? {},
        headers: CSRF ? { "X-CSRFToken": CSRF } : {},
        complete: () => requestDone(),
        ...(success ? { success: success as (data: never) => void } : {}),
        error: (xhr) => (error ?? ((e: AjaxError) => console.error("[preparation] AJAX error:", e)))(xhr as AjaxError),
    });
}

/** For requests whose dialog shows its own progress (preview, final files generation). */
export const WITHOUT_LOADING_MODAL = { spinner: false };

export function ajaxGet<T = unknown>(url: string, data?: object, callbacks?: AjaxCallbacks<T>) {
    return ajaxRequest("GET", url, data, callbacks);
}

export function ajaxPost<T = unknown>(url: string, data?: object | string, callbacks?: AjaxCallbacks<T>) {
    return ajaxRequest("POST", url, data, callbacks);
}

/** Makes htmx set up the hx-* attributes of HTML inserted by a script (htmx only does it for its own swaps). */
export function processHtmx(element: Element): void {
    (window as unknown as { htmx?: { process(element: Element): void } }).htmx?.process(element);
}
