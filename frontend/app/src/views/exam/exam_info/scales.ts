import { byId, requireData } from '@examc/helpers/dom.ts';
import { confirmDialog } from '@examc/helpers/confirm-dialog';

import { ScalesModal as AddScaleModal } from './add-scale-modal.ts';
import { SetFinalScaleModal } from './set-final-scale-modal.ts';
import { postForm } from '@examc/helpers/http.ts';
import { showToast } from '@examc/helpers/toasts.ts';


/**
 * Wires the scales section: the final scale choice for common exams, the delete confirmations
 * and the "Add scale" dialog.
 */
export function initScales(options: { 
    createScaleUrl: string; 
    finalScaleBtns: NodeListOf<HTMLButtonElement>;
    csrfToken: string;
}): void {
    const { createScaleUrl, finalScaleBtns, csrfToken } = options;
    // -----------------------------------------------------------------------
    // Final scale of an exam with common exams: for all of them, or only this one
    // -----------------------------------------------------------------------

    // Final scale of an exam with common exams: for all of them, or only this one
    for (const button of finalScaleBtns) {
        button.addEventListener("click", (e) => {
            e.preventDefault();

            const all = button.dataset["finalScaleAllUrl"];
            const one = requireData(button, "finalScaleOneUrl");
            if (all) {
                new SetFinalScaleModal({ urls: { all, one }, csrfToken }).show();
            } else {
                void postForm(one)
                    .then(() => window.location.reload())
                    .catch((error: unknown) => {
                        console.error("Making the scale official failed", error);
                        showToast("The scale could not be made official. Please try again.", { error: true });
                    });
            }
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

    byId('btn-create-scale').addEventListener('click', () => {        
        new AddScaleModal({ createScaleUrl }).show();
    });
}