import { ensureOk } from "./errors";

/**
 * Sends a GET request and returns the parsed JSON response.
 *
 * @param {string} url - The URL to fetch.
 * @return {Promise<T>} The parsed response.
 * @throws {HttpError} If the response status is not OK.
 */
export async function getJson<T>(url: string): Promise<T> {
    const response = await fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } });
    return (await (await ensureOk(response, url)).json()) as T;
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
    return (await ensureOk(response, url)).text();
}