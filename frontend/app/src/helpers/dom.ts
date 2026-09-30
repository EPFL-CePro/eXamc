/**
 * Retrieves an HTMLElement by its ID, casting it to the specified type.
 * Throws an error if no element with the given ID is found.
 *
 * @param {string} id - The ID of the element to retrieve.
 * @return {T extends HTMLElement} The HTMLElement with the specified ID, cast to the specified type.
 */
export function byId<T extends HTMLElement = HTMLElement>(id: string): T {
    const element = document.getElementById(id);
    if (!element) throw new Error(`#${id} not found`);
    return element as T;
}

/**
 * Retrieves the specified data attribute from an HTML element, throwing an error if the attribute is missing.
 *
 * @param {HTMLElement} element - The HTML element from which the data attribute will be retrieved.
 * @param {string} key - The key of the data attribute to retrieve.
 * @return {string} The value of the specified data attribute.
 */
export function requireData(element: HTMLElement, key: string): string {
    const value = element.dataset[key];
    if (!value) throw new Error(`Missing data attribute "${key}" on #${element.id}`);
    return value;
}

/**
 * Retrieves the CSRF token from a hidden input field in the DOM.
 *
 * This method searches for an input field with the name attribute set to "csrfmiddlewaretoken"
 * and returns its value. If the input field is not found, it returns an empty string.
 *
 * @return {string} The CSRF token value, or an empty string if the token is not found.
 */
export function csrfToken(): string {
    return document.querySelector<HTMLInputElement>('input[name="csrfmiddlewaretoken"]')?.value ?? '';
}

/**
 * Suspends execution for the specified number of milliseconds.
 *
 * @param {number} ms - The number of milliseconds to pause execution.
 * @return {Promise<void>} A promise that resolves after the specified delay.
 */
export function sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Creates an HTML `<i>` element with the specified class name, color, and optional title.
 *
 * @param {string} className - The class name to apply to the `<i>` element.
 * @param {string} color - The color to apply to the `<i>` element's style.
 * @param {string} [title=''] - Optional title to set as the tooltip for the `<i>` element.
 * @return {HTMLElement} The created `<i>` element with the specified attributes.
 */
export function icon(className: string, color: string, title: string = ''): HTMLElement {
    const element = document.createElement('i');
    element.className = className;
    element.style.color = color;
    if (title) element.title = title;
    return element;
}