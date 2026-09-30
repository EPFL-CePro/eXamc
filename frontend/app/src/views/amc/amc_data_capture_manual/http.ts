import { csrfToken } from '@examc/helpers/dom.ts';

/**
 * Sends a POST request with form data and returns the response text.
 *
 * @param {string} url - The URL to which the request is sent.
 * @param {Record<string, string>} body - Key-value pairs to include in the form data.
 * @return {Promise<string>} The response text from the server.
 * @throws {Error} If the response status is not OK.
 */
export async function postText(url: string, body: Record<string, string>): Promise<string> {
    const formData = new FormData();
    for (const [key, value] of Object.entries(body)) formData.append(key, value);
    formData.append('csrfmiddlewaretoken', csrfToken());

    const response = await fetch(url, { method: 'POST', body: formData, credentials: 'same-origin' });
    if (!response.ok) throw new Error(`HTTP ${response.status} on ${url}`);
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