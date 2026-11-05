import { csrfToken } from "@examc/helpers/dom.ts";
import { ensureOk } from "./errors";

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
    return ensureOk(response, url);
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