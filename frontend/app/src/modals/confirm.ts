import { ExamcModal } from "@examc/modals/base";

/** Content of a confirmation dialog. */
export interface ConfirmDialogOptions {
    title: string;
    message: string;
    /** Optional warning shown above the message. */
    warning?: string;
    confirmLabel?: string;
    cancelLabel?: string;
    /** Bootstrap button class of the confirmation, e.g. "btn-danger" for a destructive action. */
    confirmClass?: string;
}

/** A confirmation dialog, built on the fly and removed once closed. Use ConfirmModal.confirm(). */
export class ConfirmModal extends ExamcModal {
    private readonly confirmButton: HTMLButtonElement;

    private constructor({
        title,
        message,
        warning,
        confirmLabel = "Yes",
        cancelLabel = "No",
        confirmClass = "btn-primary",
    }: ConfirmDialogOptions) {
        super(ExamcModal.createElement({
            bodyContent: `
                <div class="modal-body">
                    <div class="alert alert-warning mb-3" hidden></div>
                    <p class="mb-0"></p>
                </div>
            `,
            footerContent: `
                <button type="button" class="btn btn-outline-secondary btn-sm" data-bs-dismiss="modal" data-cancel></button>
                <button type="button" class="btn btn-sm" data-confirm></button>
            `,
        }));

        // Texts are set with textContent: they may contain user content
        this.setTitle(title);
        this.element.querySelector(".modal-body p")!.textContent = message;

        const alert = this.element.querySelector<HTMLElement>(".alert")!;
        if (warning) {
            alert.innerHTML = `<i class="fa-solid fa-triangle-exclamation me-1" aria-hidden="true"></i>${warning}`;
            alert.hidden = false;
        }

        this.element.querySelector("[data-cancel]")!.textContent = cancelLabel;
        this.confirmButton = this.element.querySelector<HTMLButtonElement>("[data-confirm]")!;
        this.confirmButton.textContent = confirmLabel;
        this.confirmButton.classList.add(confirmClass);
    }

    /**
     * Shows a confirmation dialog.
     *
     * @param {ConfirmDialogOptions} options - The dialog's content.
     * @returns {Promise<boolean>} True when the user confirms, false when the dialog is dismissed.
     */
    public static confirm(options: ConfirmDialogOptions): Promise<boolean> {
        return new ConfirmModal(options).waitForConfirmation();
    }

    private waitForConfirmation(): Promise<boolean> {
        return new Promise((resolve) => {
            let confirmed = false;

            this.confirmButton.addEventListener("click", () => {
                confirmed = true;
                this.hide();
            });
            this.element.addEventListener("hidden.bs.modal", () => resolve(confirmed), { once: true });

            this.show();
        });
    }
}