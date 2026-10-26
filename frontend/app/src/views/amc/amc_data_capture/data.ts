/**
 * Reads data rendered with Django's `json_script` filter.
 *
 * @param {string} id - The id of the `<script type="application/json">` element.
 * @param {T} fallback - Returned when the element is missing, empty or not valid JSON.
 * @return {T} The parsed data.
 */
export function readJsonScript<T>(id: string, fallback: T): T {
    const text = document.getElementById(id)?.textContent;
    if (!text) return fallback;
    try {
        return JSON.parse(text) as T;
    } catch {
        console.error(`#${id} does not contain valid JSON`);
        return fallback;
    }
}

/**
 * Like readJsonScript, for data that must be an array (anything else gives an empty array).
 *
 * @param {string} id - The id of the json_script element.
 * @return {T[]} The array.
 */
export function readJsonArray<T>(id: string): T[] {
    const data = readJsonScript<unknown>(id, []);
    return Array.isArray(data) ? (data as T[]) : [];
}
