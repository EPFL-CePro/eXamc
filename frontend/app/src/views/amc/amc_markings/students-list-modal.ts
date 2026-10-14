import { ExamcModal } from '@examc/modals';
import { addStudentsTableRow, adjustStudentsTable, destroyStudentsTable } from './students-table/index.ts';

/** The dialog editing the students list, built on the fly and removed once closed. */
export class StudentsListModal extends ExamcModal {
    /**
     * @param {string} title - The dialog's title.
     * @param {() => void} onSave - Called when the user clicks "Save changes".
     */
    public constructor(title: string, onSave: () => void) {
        super(ExamcModal.createElement({
            extraDialogClass: 'modal-xl',
            // The students table looks up its container by this id.
            bodyContent: `
                <div class="modal-body">
                    <div id="students-list-table-container"></div>
                </div>
            `,
            footerContent: `
                <button type="button" class="btn btn-outline-dark btn-sm me-auto" data-add-row><i class="fas fa-plus"></i> Add student</button>
                <button type="button" class="btn btn-dark btn-sm" data-save>Save changes</button>
                <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">Close</button>
            `,
        }));

        this.setTitle(title);
        this.element.querySelector('[data-add-row]')!.addEventListener('click', addStudentsTableRow);
        this.element.querySelector('[data-save]')!.addEventListener('click', onSave);

        // DataTables measures its columns once the table is visible, and the table goes with the dialog.
        this.element.addEventListener('shown.bs.modal', adjustStudentsTable);
        this.element.addEventListener('hidden.bs.modal', destroyStudentsTable);
    }
}