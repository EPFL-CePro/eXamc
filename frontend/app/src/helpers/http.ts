import {csrfToken} from "@examc/helpers/dom.ts";

/** Form fields; an array value appends the key once per item (e.g. 'pages_list[]'). */
export type FormFields = Record<string, string | readonly string[]>;

/** A non-2xx response, keeping the body so callers can show the server's message. */
export class HttpError extends Error {
    constructor(
        readonly status: number,
        readonly url: string,
        readonly body: string,
    ) {
        super(`HTTP ${status} on ${url}`);
        this.name = 'HttpError';
    }
}

/**
 * Builds form data from fields, adding the CSRF token unless it's already there.
 *
 * @param {FormFields} fields - Fields to append.
 * @param {FormData} base - Existing form data to extend (e.g. `new FormData(form)`).
 * @return {FormData} The form data.
 */
export function toFormData(fields: FormFields = {}, base: FormData = new FormData()): FormData {
    for (const [key, value] of Object.entries(fields)) {
        if (typeof value === 'string') base.append(key, value);
        else for (const item of value) base.append(key, item);
    }
    if (!base.has('csrfmiddlewaretoken')) base.append('csrfmiddlewaretoken', csrfToken());
    return base;
}

/**
 * Sends a POST request with form data.
 *
 * @param {string} url - The URL to post to.
 * @param {FormFields} fields - Fields to send.
 * @param {FormData} base - Existing form data to extend.
 * @return {Promise<Response>} The response.
 * @throws {HttpError} If the response status is not OK.
 */
export async function postForm(url: string, fields: FormFields = {}, base?: FormData): Promise<Response> {
    const response = await fetch(url, {
        method: 'POST',
        body: toFormData(fields, base),
        credentials: 'same-origin',
    });
    if (!response.ok) throw new HttpError(response.status, url, await response.text());
    return response;
}

/** POSTs form data and returns the response text. */
export async function postText(url: string, fields: FormFields = {}): Promise<string> {
    return (await postForm(url, fields)).text();
}

/** POSTs form data and returns the parsed JSON response. */
export async function postJson<T>(url: string, fields: FormFields = {}): Promise<T> {
    return (await (await postForm(url, fields)).json()) as T;
}

/**
 * Sends a GET request and returns the parsed JSON response.
 *
 * @param {string} url - The URL to fetch.
 * @return {Promise<T>} The parsed response.
 * @throws {HttpError} If the response status is not OK.
 */
export async function getJson<T>(url: string): Promise<T> {
    const response = await fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } });
    if (!response.ok) throw new HttpError(response.status, url, await response.text());
    return (await response.json()) as T;
}

/**
 * Parses a JSON string, also unwrapping JSON that was encoded twice (a JSON string containing JSON).
 *
 * @param {string} text - The JSON string to parse. Empty or whitespace-only input returns `null`.
 * @return {T | null} The parsed value, or `null` if the input is empty.
 */
export function parseJson<T>(text: string): T | null {
    if (text.trim() === '') return null;
    let data: unknown = JSON.parse(text);
    if (typeof data === 'string') data = data.trim() === '' ? null : JSON.parse(data);
    return data as T | null;
}

/**
 * Extracts a scan path from a response that is either a plain path or a JSON-encoded string.
 *
 * @param {string} text - A plain scan path, or a JSON string containing one.
 * @return {string} The scan path.
 */
export function parseScanPath(text: string): string {
    try {
        const data: unknown = JSON.parse(text);
        if (typeof data === 'string') return data;
    } catch {
        // not JSON: plain path
    }
    return text.trim();
}

/**
 * Turns an AMC scan file path into the URL it is served from.
 *
 * @param {string} path - The scan path.
 * @return {string} The scan URL.
 */
export function toScanUrl(path: string): string {
    const parts = path.split('/');
    return `/${parts[1] ?? ''}/${parts[3] ?? ''}`;
}
