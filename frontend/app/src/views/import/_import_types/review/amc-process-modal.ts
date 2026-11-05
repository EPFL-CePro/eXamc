import { ExamcModal } from "@examc/modals";

/** Shows the live output of an AMC process. Built when opened, removed once closed. */
export class AmcProcessModal extends ExamcModal {
    private readonly body: HTMLElement;
    private readonly output: HTMLElement;

    public constructor(title: string) {
        super(ExamcModal.createElement({
            extraDialogClass: 'modal-lg modal-dialog-centered modal-dialog-scrollable',
            bodyContent: `
                <div class="modal-body">
                    <pre class="small mb-0" style="white-space: pre-wrap" data-output></pre>
                </div>
            `,
            footerContent: `
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
            `,
        }));

        this.setTitle(title);

        const body = this.element.querySelector<HTMLElement>(".modal-body");
        const output = this.element.querySelector<HTMLElement>("[data-output]");
        if (!body || !output) throw new Error('Modal body or output element not found for the AMC process modal !');
        this.body = body;
        this.output = output;
    }

    /** Everything shown so far. */
    public get text(): string {
        return this.output.textContent ?? '';
    }

    public setOutput(text = ''): void {
        this.output.textContent = text;
        this.scrollToEnd();
    }

    public appendOutput(text: string): void {
        this.output.append(text);
        this.scrollToEnd();
    }

    private scrollToEnd(): void {
        this.body.scrollTop = this.body.scrollHeight;
    }
}