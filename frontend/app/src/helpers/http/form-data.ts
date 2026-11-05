import { csrfToken } from "@examc/helpers/dom.ts";
import type { FormFields } from "./types";

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

        // An array (or other iterable): the key is appended once per item
        if (value != null && typeof value === "object" && Symbol.iterator in value) for (const item of value) base.append(key, item);
    }
    if (!base.has('csrfmiddlewaretoken')) base.append('csrfmiddlewaretoken', csrfToken());
    return base;
}