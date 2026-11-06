/**
 * Reads an array rendered with Django's `json_script` filter.
 *
 * @param {string} id - The id of the `<script type="application/json">` element.
 * @return {T[]} The array; empty when the element is missing, not valid JSON or not an array.
 */
export function readJsonArray<T>(id: string): T[] {
    const text = document.getElementById(id)?.textContent;
    if (!text) return [];
    try {
        const data: unknown = JSON.parse(text);
        return Array.isArray(data) ? (data as T[]) : [];
    } catch {
        console.error(`#${id} does not contain valid JSON`);
        return [];
    }
}
