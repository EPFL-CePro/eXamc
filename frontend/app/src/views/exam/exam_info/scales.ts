import { byId } from '@examc/helpers/dom.ts';
import { confirmDialog } from '@examc/helpers/confirm-dialog';
import { LoadingModal, LocalModal } from '@examc/modals';

import { showRequestError } from './exam.ts';

interface ScalesConfig {
    createScaleUrl: string;
}

/**
 * Wires the scales section: the final scale choice for common exams, the delete confirmations
 * and the "Add scale" dialog.
 */
export function initScales({ createScaleUrl }: ScalesConfig): void {
    // -----------------------------------------------------------------------
    // Final scale of an exam with common exams: for all of them, or only this one
    // -----------------------------------------------------------------------

    const finalModalElement = byId('final-scale-common-modal');
    const finalModal = new LocalModal(finalModalElement);
    const allForm = finalModalElement.querySelector<HTMLFormElement>('form[data-final-scale="all"]')!;
    const oneForm = finalModalElement.querySelector<HTMLFormElement>('form[data-final-scale="one"]')!;

    for (const button of document.querySelectorAll<HTMLElement>('[data-final-scale-all-url]')) {
        button.addEventListener('click', () => {
            allForm.action = button.dataset['finalScaleAllUrl'] ?? '';
            oneForm.action = button.dataset['finalScaleOneUrl'] ?? '';
            finalModal.show();
        });
    }

    // -----------------------------------------------------------------------
    // Delete confirmations
    // -----------------------------------------------------------------------

    for (const form of document.querySelectorAll<HTMLFormElement>('form[data-confirm]')) {
        form.addEventListener('submit', (event) => {
            event.preventDefault();
            void confirmDialog({
                title: 'Delete scale',
                message: form.dataset['confirm'] ?? 'Delete this scale?',
                warning: 'This cannot be undone.',
                confirmLabel: 'Delete',
                confirmClass: 'btn-danger',
            }).then((confirmed) => {
                if (confirmed) form.submit(); // submit() doesn't fire this listener again
            });
        });
    }

    // -----------------------------------------------------------------------
    // "Add scale": the server's form, loaded into the dialog and submitted in it
    // -----------------------------------------------------------------------

    const createModalElement = byId('create-scale-modal');
    const createModal = new LocalModal(createModalElement);
    const content = createModalElement.querySelector<HTMLElement>('.modal-content')!;

    byId('btn-create-scale').addEventListener('click', () => {
        void (async () => {
            try {
                const html = await new LoadingModal(async () => {
                    const response = await fetch(createScaleUrl, { credentials: 'same-origin' });
                    if (!response.ok) throw new Error(`Create scale form request failed: ${response.status}`);
                    return response.text();
                }).result;
                content.innerHTML = html; // the server's own form template
                createModal.show();
            } catch (error) {
                showRequestError(error, 'The scale form could not be loaded.');
            }
        })();
    });

    // A valid form redirects (the scale was created); an invalid one comes back with its errors.
    content.addEventListener('submit', (event) => {
        const form = event.target;
        if (!(form instanceof HTMLFormElement)) return;
        event.preventDefault();

        void (async () => {
            try {
                const response = await fetch(form.action || createScaleUrl, {
                    method: 'POST',
                    body: new FormData(form),
                    credentials: 'same-origin',
                });
                if (response.redirected) {
                    window.location.reload();
                    return;
                }
                if (!response.ok) throw new Error(`Create scale request failed: ${response.status}`);
                content.innerHTML = await response.text();
            } catch (error) {
                showRequestError(error, 'The scale could not be created.');
            }
        })();
    });
}