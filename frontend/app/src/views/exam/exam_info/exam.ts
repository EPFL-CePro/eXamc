import { byId } from '@examc/helpers/dom.ts';
import { HttpError, postText } from '@examc/helpers/http.ts';
import { LoadingModal, LocalModal } from '@examc/modals';
import { PdfModal } from '@examc/modals/pdf';

declare global {
    interface Window {
        /** Shows a user-facing error sent by the server (errors/_user_facing_error_modal.html). */
        showUserError?: (payload: unknown) => void;
    }
}

/**
 * The text fields of a form, CSRF token included.
 *
 * @param {HTMLFormElement} form - The form.
 * @return {Record<string, string>} The fields.
 */
export function formFields(form: HTMLFormElement): Record<string, string> {
    const fields: Record<string, string> = {};
    for (const [key, value] of new FormData(form)) {
        if (typeof value === 'string') fields[key] = value;
    }
    return fields;
}

/**
 * Shows a failed request: the server's user-facing error when it sent one, else a message in the info modal.
 *
 * @param {unknown} error - What the request threw.
 * @param {string} message - The message shown otherwise.
 */
export function showRequestError(error: unknown, message: string): void {
    console.error(error);

    if (error instanceof HttpError && window.showUserError) {
        try {
            window.showUserError(JSON.parse(error.body));
            return;
        } catch {
            // Not JSON: fall through to the generic message.
        }
    }

    byId('ajax-info-modal-msg').textContent = message;
    new LocalModal(byId('ajax-info-modal')).show();
}

/**
 * Posts a form's fields, then reloads the page to show the saved state.
 *
 * @param {HTMLFormElement} form - The form.
 * @param {string} url - Where to post it.
 * @param {string} errorMessage - Shown if saving fails.
 */
function submitAndReload(form: HTMLFormElement, url: string, errorMessage: string): void {
    form.addEventListener('submit', (event) => {
        event.preventDefault();
        void (async () => {
            try {
                await new LoadingModal(() => postText(url, formFields(form))).result;
                window.location.reload();
            } catch (error) {
                showRequestError(error, errorMessage);
            }
        })();
    });
}

/** The exam's code, name, year, semester and date. */
export function initExamInfo(form: HTMLFormElement, url: string): void {
    submitAndReload(form, url, 'The exam info could not be saved.');
}

/** The exam's modules (review, AMC, results & stats, preparation). */
export function initExamOptions(form: HTMLFormElement, url: string): void {
    submitAndReload(form, url, 'The modules could not be saved.');
}

/**
 * The catalog PDF dialog. The PDF is only loaded the first time the dialog opens.
 */
export function initCatalog(options: { button: HTMLButtonElement; url: string }): void {
    const { button, url } = options;

    button.addEventListener("click", () => {
        PdfModal.open({ title: "Catalog", url });
    });
}