import type { ExamcModalOptions } from "@examc/types/modals";
import { ExamcModal } from "@examc/modals/base";
import { SimpleEditor } from "@examc/editors/simple";

import "./editor.scss";

type EditorFormat = "html" | "markdown";

interface EditOptions {
    /** The modal's title. */
    title?: string;
    /** The initial content, as Markdown or HTML depending on the format (HTML by default). */
    content?: string;
    /** The format the edited content is returned in. */
    format?: EditorFormat;
    /** Called with the content on save; if it throws, the modal stays open and shows the error. */
    onSave?: (content: string) => Promise<void> | void;
}

interface PendingEdit {
    resolve: (content: string | null) => void;
    format: EditorFormat;
    onSave: ((content: string) => Promise<void> | void) | undefined;
    /** The content as Markdown when the edit started, to detect changes. */
    baseline: string;
}

/**
 * A modal editing formatted text with the simple editor.
 * `edit()` resolves with the saved content, or null if the modal was closed without saving.
 * Saving is only possible after a change, and closing with unsaved changes asks for confirmation.
 * Built on the fly unless an element is given.
 */
export class EditorModal extends ExamcModal {
    private readonly editor: Promise<SimpleEditor>;
    private readyEditor: SimpleEditor | null = null;
    private readonly titleElement: HTMLElement;
    private readonly saveButton: HTMLButtonElement;
    private readonly errorElement: HTMLElement;
    private pending: PendingEdit | null = null;
    /** Set when closing is confirmed or follows a save, so the close isn't asked about again. */
    private closeAllowed: boolean = false;

    public constructor(options: { element?: HTMLElement | null; modalOptions?: ExamcModalOptions } = {}) {
        super(options.element ?? EditorModal.createEditorElement(), options.modalOptions);

        const target = this.element.querySelector<HTMLElement>(".modal-body [data-editor]");
        const titleElement = this.element.querySelector<HTMLElement>(".modal-title");
        const saveButton = this.element.querySelector<HTMLButtonElement>("[data-editor-save]");
        const errorElement = this.element.querySelector<HTMLElement>("[data-editor-error]");
        if (!target || !titleElement || !saveButton || !errorElement) {
            throw new Error("An editor modal needs a title, an editor element, an error element and a save button.");
        }

        this.titleElement = titleElement;
        this.saveButton = saveButton;
        this.errorElement = errorElement;

        this.editor = SimpleEditor.create({
            target,
            format: "html",
            onChange: (markdown) => this.updateSaveButton(markdown),
        });
        void this.editor.then((editor) => { this.readyEditor = editor; });

        this.saveButton.addEventListener("click", () => void this.save());
        this.element.addEventListener("shown.bs.modal", () => void this.editor.then((editor) => editor.focus()));

        // Close button, Escape and backdrop all go through Bootstrap's hide event, which can be cancelled.
        this.element.addEventListener("hide.bs.modal", (event: Event) => {
            if (this.closeAllowed || !this.hasChanges()) return;
            event.preventDefault();
            if (window.confirm("You have unsaved changes. Close and discard them?")) {
                this.closeAllowed = true;
                this.hide();
            }
        });

        // Closing without saving resolves the edit with null.
        this.element.addEventListener("hidden.bs.modal", () => this.settle(null));
    }

    /**
     * Opens the modal to edit some content. An edit still open is resolved with null first.
     *
     * @return {Promise<string | null>} The saved content in the requested format, or null if closed without saving.
     */
    public async edit({ title = "Edit", content = "", format = "html", onSave }: EditOptions = {}): Promise<string | null> {
        this.settle(null);

        const editor = await this.editor;
        editor.setContent(content);
        this.titleElement.textContent = title;
        this.setError(null);
        this.closeAllowed = false;

        const baseline: string = editor.getContent("markdown");
        this.saveButton.disabled = true;

        return new Promise((resolve) => {
            this.pending = { resolve, format, onSave, baseline };
            this.show();
        });
    }

    private hasChanges(): boolean {
        if (!this.pending || !this.readyEditor) return false;
        return this.readyEditor.getContent("markdown") !== this.pending.baseline;
    }

    private updateSaveButton(markdown: string): void {
        this.saveButton.disabled = !this.pending || markdown === this.pending.baseline;
    }

    private async save(): Promise<void> {
        const pending = this.pending;
        if (!pending || !this.hasChanges()) return;

        const editor = await this.editor;
        const content = editor.getContent(pending.format);

        if (pending.onSave) {
            this.saveButton.disabled = true;
            this.setError(null);
            try {
                await pending.onSave(content);
            } catch (error: unknown) {
                this.setError(error instanceof Error ? error.message : "Could not save the changes.");
                this.saveButton.disabled = false;
                return;
            }
        }

        // Settled before hiding, so the hide and hidden events find nothing left to guard or resolve.
        this.settle(content);
        this.closeAllowed = true;
        this.hide();
    }

    private settle(content: string | null): void {
        const pending = this.pending;
        this.pending = null;
        pending?.resolve(content);
    }

    private setError(message: string | null): void {
        this.errorElement.textContent = message ?? "";
        this.errorElement.hidden = message === null;
    }

    private static createEditorElement(): HTMLElement {
        return ExamcModal.createElement({
            extraDialogClass: "modal-xl examc-editor-modal",
            bodyContent: `
                <div class="modal-body">
                    <div class="alert alert-danger" role="alert" data-editor-error hidden></div>
                    <div data-editor></div>
                </div>
            `,
            footerContent: `
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                <button type="button" class="btn btn-primary" data-editor-save disabled>
                    <i class="fas fa-floppy-disk"></i> Save changes
                </button>
            `,
        });
    }
}