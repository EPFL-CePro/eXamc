import { ExamcModal } from '@examc/modals/base.ts';
import type { UserFacingError } from '@examc/types/errors';


const DEFAULT_TITLE = 'Something went wrong';
const DEFAULT_DETAIL = 'Please try again or contact support.';

/** Shows a UserFacingError, with an optional action link. Built on the fly and removed once closed. */
export class ErrorModal extends ExamcModal {
    /**
     * @param {UserFacingError} [error] - The error; missing fields get a generic text.
     */
    public constructor(error: UserFacingError = {}) {
        super(ExamcModal.createElement({
            extraDialogClass: 'modal-dialog-centered',
            bodyContent: `
                <div class="modal-body">
                    <p class="mb-0" style="white-space: pre-line" data-message></p>
                </div>
            `,
            footerContent: `
                <a class="btn btn-primary" data-action hidden></a>
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
            `,
        }));

        this.setTitle("⚠️ " + error.title || DEFAULT_TITLE);

        const message = this.element.querySelector<HTMLElement>('[data-message]')!;
        if (error.detail_html) {
            message.innerHTML = error.detail_html; // rendered by the server, variables escaped
        } else {
            message.textContent = error.detail || DEFAULT_DETAIL;
        }

        if (error.action_url) {
            const action = this.element.querySelector<HTMLAnchorElement>('[data-action]')!;
            action.href = error.action_url;
            action.textContent = error.action_label || 'Continue';
            action.hidden = false;
        }
    }
}
