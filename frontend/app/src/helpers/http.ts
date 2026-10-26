import {csrfToken} from "@examc/helpers/dom.ts";

/** Form fields; an array value appends the key once per item (e.g. 'pages_list[]'). */
export type FormFields = Record<string, boolean | number | string | readonly string[]>;

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
 * Reads a response body as text, passing each chunk on as it arrives.
 * Without a readable body, the whole text is passed at once.
 *
 * @param {Response} response - The response to read.
 * @param {(text: string) => void} onText - Called with each decoded chunk.
 */
export async function readTextStream(response: Response, onText: (text: string) => void): Promise<void> {
    if (!response.body) {
        onText(await response.text());
        return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        onText(decoder.decode(value, { stream: true }));
    }

    // Flushes a multi-byte character split across the last chunks
    const rest = decoder.decode();
    if (rest) onText(rest);
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
        if (typeof value === "string") base.append(key, value);
        if (typeof value === "boolean") base.append(key, value ? "true" : "false");
        if (typeof value === "number") base.append(key, String(value));

        // is it an iterator check
        if (value != null && typeof value === "object" && Symbol.iterator in value) for (const item of value) base.append(key, item);
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
 * Sends a GET request and returns the response text.
 *
 * @param {string} url - The URL to fetch.
 * @return {Promise<string>} The response text.
 * @throws {HttpError} If the response status is not OK.
 */
export async function getText(url: string): Promise<string> {
    const response = await fetch(url, { credentials: 'same-origin' });
    if (!response.ok) throw new HttpError(response.status, url, await response.text());
    return response.text();
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
 * Turns an AMC scan file path into the URL it is served from.
 *
 * @param {string} path - The scan path.
 * @return {string} The scan URL.
 */
export function toScanUrl(path: string): string {
    const parts = path.split('/');
    return `/${parts[1] ?? ''}/${parts[3] ?? ''}`;
}


/**
 * Sends a request with a JSON body (PATCH, PUT, DELETE or POST), with the CSRF token in the headers.
 *
 * @param {string} method - The HTTP method.
 * @param {string} url - The URL to send to.
 * @param {unknown} body - What is sent, as JSON.
 * @return {Promise<Response>} The response.
 * @throws {HttpError} If the response status is not OK.
 */
export async function sendJson(method: string, url: string, body: unknown): Promise<Response> {
    const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
        body: JSON.stringify(body),
        credentials: 'same-origin',
    });
    if (!response.ok) throw new HttpError(response.status, url, await response.text());
    return response;
}

/** A failed request: the status (0 when the server was not reached), and what the server answered. */
export interface RequestFailure {
    status: number;
    text: string;
    json: unknown;
}

/**
 * Describes why a request failed.
 *
 * @param {unknown} error - What the request threw: an HttpError when the server answered with an error.
 * @return {RequestFailure} The status (0 when the server was not reached), the answer as text and as JSON if it is.
 */
export function describeFailure(error: unknown): RequestFailure {
    if (!(error instanceof HttpError)) {
        return { status: 0, text: error instanceof Error ? error.message : String(error), json: undefined };
    }

    let json: unknown;
    try {
        json = JSON.parse(error.body);
    } catch {
        json = undefined;
    }
    return { status: error.status, text: error.body, json };
}

/** The JSON body of a failed request, or an empty object. */
export function failureJson<T extends object>(failure: RequestFailure): Partial<T> {
    return (failure.json ?? {}) as Partial<T>;
}


/**
 * The file name a response gives in its Content-Disposition header, if any
 * (filename*=UTF-8''… first, as it holds non-ASCII names, then filename="…").
 */
function attachmentFileName(response: Response): string | null {
    const header = response.headers.get('Content-Disposition') ?? '';
    const encoded = /filename\*=UTF-8''([^;]+)/i.exec(header)?.[1];
    if (encoded) return decodeURIComponent(encoded);
    return /filename="?([^";]+)"?/i.exec(header)?.[1] ?? null;
}

/**
 * Downloads a file: fetches it, then has the browser save it under the server's file name.
 *
 * @param {string} url - The file's URL.
 * @param {string} fallbackName - The name to use if the server gives none.
 * @throws {HttpError} If the response status is not OK.
 */
export async function downloadFile(url: string, fallbackName: string): Promise<void> {
    const response = await fetch(url, { credentials: 'same-origin' });
    if (!response.ok) throw new HttpError(response.status, url, await response.text());

    const objectUrl = URL.createObjectURL(await response.blob());
    const link = document.createElement('a');
    link.href = objectUrl;
    link.download = attachmentFileName(response) ?? fallbackName;
    link.click();
    // Freed once the browser has started saving the file
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}