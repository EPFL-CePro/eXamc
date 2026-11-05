import type { FormFields } from "./types";
import { ensureOk } from "./errors";
import { toFormData } from "./form-data";

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
    return ensureOk(response, url);
}

/** POSTs form data and returns the response text. */
export async function postText(url: string, fields: FormFields = {}): Promise<string> {
    return (await postForm(url, fields)).text();
}

/** POSTs form data and returns the parsed JSON response. */
export async function postJson<T>(url: string, fields: FormFields = {}): Promise<T> {
    return (await (await postForm(url, fields)).json()) as T;
}