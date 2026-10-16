import type { ExamcModalOptions } from "@examc/types/modals";
import { ExamcModal } from "@examc/modals/base";

/** Distance from the bottom (in px) under which the output still counts as scrolled to its end. */
const END_THRESHOLD_PX = 20;

/**
 * A modal showing a log in a textarea, which follows the end of the log as it grows
 * unless the user scrolled away from the end. Built on the fly unless an element is given.
 */
export class LogModal extends ExamcModal {
    private readonly output: HTMLTextAreaElement;

    public constructor(options: { element?: HTMLElement | null; modalOptions?: ExamcModalOptions } = {}) {
        super(options.element ?? LogModal.createLogElement(), options.modalOptions);

        const output = this.element.querySelector<HTMLTextAreaElement>(".modal-body textarea");
        if (!output) throw new Error("A log modal needs a textarea in its body.");
        this.output = output;

        this.scrollToEndWhenShown();
    }

    public setOutput(content: string): void {
        this.updateOutput(() => {
            this.output.value = content;
        });
    }

    public appendToOutput(content: string): void {
        this.updateOutput(() => {
            this.output.value += content;
        });
    }

    /**
     * Changes the output, following its end as it grows unless the user scrolled away from the end.
     * Scrolling back to the end follows the output again.
     */
    private updateOutput(update: () => void): void {
        const { output } = this;
        const isVisible = output.clientHeight > 0;
        const wasAtEnd = output.scrollHeight - output.scrollTop - output.clientHeight <= END_THRESHOLD_PX;
        update();

        // While hidden, the output can't be scrolled: scrollToEndWhenShown scrolls it once the modal is visible.
        if (isVisible && wasAtEnd) this.scrollToEnd();
    }

    private scrollToEnd(): void {
        this.output.scrollTop = this.output.scrollHeight;
    }

    /**
     * Scrolls to the end as soon as the output becomes visible: ResizeObserver callbacks run after layout
     * but before paint, so the user never sees the output at the top first.
     */
    private scrollToEndWhenShown(): void {
        let wasVisible = false;
        new ResizeObserver(([entry]) => {
            const isVisible = (entry?.contentRect.height ?? 0) > 0;
            if (isVisible && !wasVisible) this.scrollToEnd();
            wasVisible = isVisible;
        }).observe(this.output);
    }

    private static createLogElement(): HTMLElement {
        return ExamcModal.createElement({
            extraDialogClass: 'modal-xl',
            bodyContent: `
                <div class="modal-body">
                    <textarea readonly style="height: 76vh; padding: 1rem; resize: none; background: black; color: white; width: 100%"></textarea>
                </div>
            `,
            footerContent: `<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>`,
        });
    }
}