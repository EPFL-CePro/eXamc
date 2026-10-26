import { postForm } from '@examc/helpers/http.ts';
import { LocalModal } from '@examc/modals/local.ts';

/**
 * Saves the print settings without leaving the page, and closes their dialog once saved.
 * The submit button is disabled while the request runs, so the settings aren't sent twice.
 *
 * @param form - The print settings form (its action is the save URL, its fields include the CSRF token).
 * @param modalElement - The dialog holding the form.
 */
export function initPrintSettings(form: HTMLFormElement, modalElement: HTMLElement): void {
    const modal = new LocalModal(modalElement);

    form.addEventListener('submit', (event) => {
        event.preventDefault();

        const submitButton = form.querySelector<HTMLButtonElement>('button[type="submit"]');
        if (submitButton) submitButton.disabled = true;

        postForm(form.action, {}, new FormData(form))
            .then(() => modal.hide())
            .catch((error: unknown) => {
                console.error('Could not save the print settings', error);
                window.alert('The print settings could not be saved. Please try again.');
            })
            .finally(() => {
                if (submitButton) submitButton.disabled = false;
            });
    });
}