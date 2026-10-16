import { getPageBootstrap } from "@examc/helpers/page-bootstrap";

import { CSRF, Selectors } from "./config.ts";

export function getElement<T extends HTMLElement = HTMLElement>(selector: string): T | null {
    return document.querySelector<T>(selector);
}

function getModalInstance(selector: string) {
    const element = getElement(selector);
    if (!element) return null;
    return getPageBootstrap().Modal.getOrCreateInstance(element);
}

export function showModal(selector: string): void {
    getModalInstance(selector)?.show();
}

export function hideModal(selector: string): void {
    const element = getElement(selector);
    if (!element) return;
    getPageBootstrap().Modal.getInstance(element)?.hide();
}

function showLoading(show: boolean): void {
    const modal = getModalInstance(Selectors.loadingModal);
    if (!modal) return;

    if (show) modal.show();
    else modal.hide();
}

/** What the callbacks of a failed request get (the jqXHR of jQuery). */
export interface AjaxError {
    status: number;
    responseText: string;
    responseJSON?: unknown;
}

export interface AjaxCallbacks<T> {
    beforeSend?: () => void;
    complete?: () => void;
    success?: (data: T) => void;
    error?: (xhr: AjaxError) => void;
}

function ajaxRequest<T>(method: "GET" | "POST", url: string, data: object | string | undefined, callbacks: AjaxCallbacks<T> = {}) {
    const { beforeSend, complete, success, error } = callbacks;
    return $.ajax({
        url,
        type: method,
        data: data ?? {},
        headers: CSRF ? { "X-CSRFToken": CSRF } : {},
        beforeSend: beforeSend ?? (() => showLoading(true)),
        complete: complete ?? (() => showLoading(false)),
        ...(success ? { success: success as (data: never) => void } : {}),
        error: (xhr) => (error ?? ((e: AjaxError) => console.error("[preparation] AJAX error:", e)))(xhr as AjaxError),
    });
}

/** For requests whose dialog shows its own progress (preview, final files generation). */
export const WITHOUT_LOADING_MODAL = {
    beforeSend: () => undefined,
    complete: () => undefined,
};

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
