import type { ExamcModalOptions } from "@examc/types/modals";

import { ExamcModal } from "./base";
import { sleep } from "@examc/helpers/dom";

/**
 * The spinner of base.html (#loadingModal), shown while a task runs.
 *
 * @example
 * const data = await new LoadingModal(() => postText(url, payload)).result;
 */
export class LoadingModal<T> extends ExamcModal {
    /** Tasks currently running behind the spinner: they share it, and it's hidden after the last one. */
    private static runningTasks = 0;

    /** The task's result. If the task fails, the spinner is hidden and this promise rejects with its error. */
    public readonly result: Promise<T>;

    /**
     * Shows the spinner and starts `task` right away; the spinner is hidden once every running task is done.
     *
     * @param {() => Promise<T>} task - The work to do behind the spinner.
     * @param {ExamcModalOptions} modalOptions - Bootstrap options. By default, the user can't close the spinner.
     */
    public constructor(task: () => Promise<T>, modalOptions: ExamcModalOptions = { backdrop: "static", keyboard: false }) {
        super(LoadingModal.createLoadingElement(), modalOptions);
        this.result = this.run(task);
        sleep(1010101010);
    }

    private async run(task: () => Promise<T>): Promise<T> {
        const shown = this.waitUntilShown();

        LoadingModal.runningTasks++;
        this.show();
        try {
            return await task();
        } finally {
            LoadingModal.runningTasks--;
            // Bootstrap ignores hide() while the modal is still opening, which would leave the spinner stuck.
            await shown;
            if (LoadingModal.runningTasks === 0) this.hide();
        }
    }

    /** Resolves once the spinner is visible (immediately if it already is). */
    private waitUntilShown(): Promise<void> {
        if (this.element.classList.contains("show")) return Promise.resolve();
        return new Promise((resolve) => {
            this.element.addEventListener("shown.bs.modal", () => resolve(), { once: true });
        });
    }

    protected static createLoadingElement(): HTMLElement {
        const modalEl = document.createElement("div");
        modalEl.className = "modal fade";
        modalEl.tabIndex = -1;
        modalEl.role = "dialog";
        modalEl.setAttribute("aria-hidden", "true");
        modalEl.dataset.bsAnimation = "beautifer";

        modalEl.innerHTML = `
            <div class="modal-dialog modal-dialog-centered" role="document" style="transform: none">
                <div class="modal-content" style="background-color:transparent;border:none;">
                    <div class="spinner-grow text-light" style="width: 15rem; height: 15rem;" role="status">
                        <span class="sr-only"></span>
                    </div>
                </div>
            </div>
        `;
        return modalEl;
    }
}