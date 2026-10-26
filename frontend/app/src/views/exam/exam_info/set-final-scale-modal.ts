import { ExamcModal } from "@examc/modals";

/** The URLs setting a scale as the final one: for every exam of the group, or only for this exam. */
export interface FinalScaleUrls {
    all: string;
    one: string;
}

/**
 * Asks whether a final scale applies to all the exams of a group, or only to this exam, then submits the choice.
 * Built on the fly and removed once closed. Use SetFinalScaleModal.open().
 */
export class SetFinalScaleModal extends ExamcModal {
    public constructor(options: { urls: FinalScaleUrls; csrfToken: string }) {
        const { urls, csrfToken } = options;

        super(ExamcModal.createElement({
            titleContent: "Final scale for common exams",
            bodyContent: `
                <div class="modal-body">
                    <p class="mb-0">Do you want to set this final scale for all common exams?</p>
                </div>`,
            footerContent: `
                <form method="post" data-final-scale="one">
                    <input type="hidden" name="csrfmiddlewaretoken">
                    <button type="submit" class="btn btn-outline-dark btn-sm">For this exam</button>
                </form>

                <form method="post" data-final-scale="all" class="me-auto">
                    <input type="hidden" name="csrfmiddlewaretoken">
                    <button type="submit" class="btn btn-dark btn-sm">For all common exams</button>
                </form>

                <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">Cancel</button>
            `,
        }));

        // Set with the DOM: the URLs and the token are data, not markup
        for (const [choice, url] of Object.entries(urls)) {
            const form = this.element.querySelector<HTMLFormElement>(`form[data-final-scale="${choice}"]`)!;
            form.action = url;
            form.querySelector<HTMLInputElement>('input[name="csrfmiddlewaretoken"]')!.value = csrfToken;
        }
    }
}