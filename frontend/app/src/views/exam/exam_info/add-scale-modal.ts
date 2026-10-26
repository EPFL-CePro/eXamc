import { ExamcModal } from "@examc/modals";
import { showRequestError } from "./exam";


export class ScalesModal extends ExamcModal {
    private readonly createScaleUrl: string;
    private modalBody: HTMLDivElement;

    public constructor(options: { createScaleUrl: string } ) {        
        super(ExamcModal.createElement({
            extraDialogClass: 'modal-lg',
            bodyContent: `
                <div class="modal-body"></div>
            `,
            footerContent: `
                <span class="small text-muted me-auto mr-auto" data-status role="status"></span>
                <button type="button" class="btn btn-success" data-save>Add</button>
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
            `,
        }));

        this.createScaleUrl = options.createScaleUrl;

        this.setTitle("Add scale");

        const modalBody = this.element.querySelector<HTMLDivElement>(".modal-body");
        const validateBtn = this.element.querySelector<HTMLButtonElement>("button[data-save]");

        if (!modalBody || !validateBtn) throw new Error('Modal body element or validate button element not found for the scales modal !');
        this.modalBody = modalBody;

        try {
            fetch(this.createScaleUrl, { credentials: 'same-origin' })
                .then(response => response.text())
                .then(html => {
                    modalBody.innerHTML = html;
                    
                    const form = this.element.querySelector<HTMLFormElement>("form");
                    if (!form) throw new Error(`Server response for url ${this.createScaleUrl} didn't contain the expected form element !`);
                    
                    
                    validateBtn.addEventListener("click", (event) => {
                        event.preventDefault();
                        this.submitAddScaleForm(form);
                    });
                });
            
        } catch (error) {
            showRequestError(error, 'The scale form could not be loaded.');
        }
    }

    private async submitAddScaleForm(form: HTMLFormElement): Promise<void> {
        try {
            const response = await fetch(form.action || this.createScaleUrl, {
                method: 'POST',
                body: new FormData(form),
                credentials: 'same-origin',
            });

            if (response.redirected) {
                window.location.reload();
                return;
            }

            if (!response.ok) throw new Error(`Create scale request failed: ${response.status}`);
            this.modalBody.innerHTML = await response.text();
        } catch (error) {
            showRequestError(error, 'The scale could not be created.');
        }
    }
}