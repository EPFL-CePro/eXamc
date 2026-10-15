import type { Api } from 'datatables.net-bs5';

import { SimpleEditor } from '@examc/editors';
import { ExamcModal } from '@examc/modals/base.ts';

import { buildSendTable, columnKeys, selectedStudents } from './table.ts';
import type { EmailDraft, SendRequest, StudentRow } from './types.ts';

/** Column selected by default for the email addresses. */
const DEFAULT_EMAIL_COLUMN = 'EMAIL';

export interface SendPapersModalOptions {
    /** The students, one table row each. */
    rows: StudentRow[];
    /** The email to start from. */
    draft: EmailDraft;
    /** Sends the papers. The dialog closes once it resolves; if it throws, it stays open with an error. */
    onSend: (request: SendRequest) => Promise<void>;
    /** Called once the dialog is closed: the email as it was left, or null once the papers were sent. */
    onClose: (draft: EmailDraft | null) => void;
}

/** Ids of the dialog's fields: unique, in case a dialog is opened while another is still closing. */
let dialogCount = 0;

/** The "Send annotated papers" dialog, built on the fly and removed once closed. */
export class SendPapersModal extends ExamcModal {
    private readonly options: SendPapersModalOptions;
    private readonly table: Api<StudentRow>;
    private readonly editor: Promise<SimpleEditor>;
    private editorInstance: SimpleEditor | null = null;

    private readonly alertEl: HTMLElement;
    private readonly columnSelect: HTMLSelectElement;
    private readonly subjectInput: HTMLInputElement;
    private readonly sendButton: HTMLButtonElement;

    /** Set once the papers were sent: the draft is then dropped. */
    private sent = false;
    /** The email as it was when the dialog started closing. */
    private closingDraft: EmailDraft | null = null;

    public constructor(options: SendPapersModalOptions) {
        const id = `send-papers-${++dialogCount}`;

        super(ExamcModal.createElement({
            extraDialogClass: 'modal-xl',
            bodyContent: `
                <div class="modal-body">
                    <div class="alert text-center" role="alert" data-alert hidden></div>

                    <h6>Addresses</h6>
                    <div class="input-group input-group-sm w-auto mb-2">
                        <label class="input-group-text" for="${id}-column">Emails column</label>
                        <select class="form-select" id="${id}-column" data-email-column></select>
                    </div>
                    <table class="table table-striped w-100" data-students></table>

                    <hr>

                    <label class="form-label fw-semibold" for="${id}-subject">Subject</label>
                    <input type="text" class="form-control form-control-sm mb-3" id="${id}-subject" data-subject>

                    <div class="form-label fw-semibold" id="${id}-body-label">Body</div>
                    <div data-body aria-labelledby="${id}-body-label"></div>
                </div>
            `,
            footerContent: `
                <button type="button" class="btn btn-dark btn-sm" data-send>Send</button>
                <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">Close</button>
            `,
        }));

        this.options = options;
        this.setTitle('Send annotated papers');

        this.alertEl = this.element.querySelector<HTMLElement>('[data-alert]')!;
        this.columnSelect = this.element.querySelector<HTMLSelectElement>('[data-email-column]')!;
        this.subjectInput = this.element.querySelector<HTMLInputElement>('[data-subject]')!;
        this.sendButton = this.element.querySelector<HTMLButtonElement>('[data-send]')!;

        // Email column: any column of the students list, EMAIL by default
        for (const key of columnKeys(options.rows)) {
            this.columnSelect.add(new Option(key, key, false, key === DEFAULT_EMAIL_COLUMN));
        }

        this.subjectInput.value = options.draft.subject;
        this.table = buildSendTable(this.element.querySelector<HTMLTableElement>('[data-students]')!, options.rows);
        this.editor = SimpleEditor.create({
            target: this.element.querySelector<HTMLElement>('[data-body]')!,
            defaultValue: options.draft.body,
        });
        void this.editor.then((editor) => (this.editorInstance = editor));

        this.sendButton.addEventListener('click', () => void this.send());

        // The table was built while hidden: its columns are measured once it's visible.
        this.element.addEventListener('shown.bs.modal', () => this.table.columns.adjust());
        this.element.addEventListener('hide.bs.modal', () => {
            this.closingDraft = this.sent ? null : this.currentDraft();
        });
        this.element.addEventListener('hidden.bs.modal', () => {
            this.table.destroy();
            void this.editor.then((editor) => editor.destroy());
            options.onClose(this.closingDraft);
        });
    }

    /** The email as currently written. */
    private currentDraft(): EmailDraft {
        return {
            subject: this.subjectInput.value,
            body: this.editorInstance?.getContent('markdown') ?? this.options.draft.body,
        };
    }

    /**
     * Shows a message above the form, or hides it.
     *
     * @param {'warning' | 'danger' | null} level - The alert's color, or null to hide it.
     * @param {string} [message] - The message.
     */
    private showAlert(level: 'warning' | 'danger' | null, message = ''): void {
        this.alertEl.hidden = level === null;
        this.alertEl.classList.toggle('alert-warning', level === 'warning');
        this.alertEl.classList.toggle('alert-danger', level === 'danger');
        this.alertEl.textContent = message;
    }

    private async send(): Promise<void> {
        const editor = this.editorInstance;
        if (!editor) return; // editor still loading

        const subject = this.subjectInput.value.trim();
        const students = selectedStudents(this.table, this.options.rows, this.columnSelect.value);
        const isBodyEmpty = editor.getContent('markdown').trim() === '';

        if (students.length === 0 || subject === '' || isBodyEmpty) {
            this.showAlert('warning', 'Please select at least one address and enter a subject and a body for the email!');
            return;
        }
        this.showAlert(null);

        const label = this.sendButton.textContent;
        this.sendButton.disabled = true;
        this.sendButton.textContent = 'Sending…';

        try {
            await this.options.onSend({
                emailColumn: this.columnSelect.value,
                subject,
                body: editor.getContent('html'),
                students,
            });
            this.sent = true;
            this.hide();
        } catch (error) {
            console.error(error);
            this.showAlert('danger', 'The annotated papers could not be sent. Please try again.');
        } finally {
            this.sendButton.disabled = false;
            this.sendButton.textContent = label;
        }
    }
}