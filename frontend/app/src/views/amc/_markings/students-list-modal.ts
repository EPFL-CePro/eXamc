import DataTable, { type Api, type ApiCellMethods, type ColumnOptions } from 'datatables.net-bs5';
import 'datatables.net-bs5/css';
import 'datatables.net-keytable-bs5';
import 'datatables.net-keytable-bs5/css';

import { setupDatatables } from '@examc/helpers/datatables.ts';
import { ExamcModal } from '@examc/modals/base.ts';

import type { StudentsListRow } from './types.ts';

/** Class of the CSV columns: the only ones KeyTable can focus. */
const CELL_CLASS = 'students-list-cell';
const DELETE_BUTTON_CLASS = 'students-list-delete';

/** Key codes KeyTable passes to its `key` event. */
const KEY = { backspace: 8, enter: 13, delete: 46, f2: 113 } as const;

export interface StudentsListModalOptions {
    title: string;
    /** The CSV header: one column each. */
    header: string[];
    rows: StudentsListRow[];
    /**
     * Saves the edited rows. The dialog closes once it resolves; if it throws, the dialog stays open
     * and shows the error's message.
     */
    onSave: (rows: StudentsListRow[]) => Promise<void>;
}

/**
 * Builds the column definitions: one per CSV column, then the delete button column.
 * Column types are left to DataTables' built-in detection.
 *
 * @param {string[]} header - The CSV header.
 * @return {ColumnOptions[]} The columns.
 */
function buildColumns(header: string[]): ColumnOptions[] {
    const columns: ColumnOptions[] = header.map((title, index) => ({
        title,
        data: index,
        className: CELL_CLASS,
        render: DataTable.render.text(), // values are shown as typed, never as HTML
    }));

    columns.push({
        title: '',
        data: null,
        orderable: false,
        searchable: false,
        className: 'text-center',
        render: () => `<button type="button" class="btn btn-sm btn-outline-danger ${DELETE_BUTTON_CLASS}" `
            + 'title="Delete row" aria-label="Delete row"><i class="fa-solid fa-trash" aria-hidden="true"></i></button>',
    });

    return columns;
}

/**
 * The dialog editing the students list in an editable table, built on the fly and removed once closed.
 *
 * Keyboard: arrows move between cells, Enter or F2 edits, typing replaces the value, Delete or Backspace
 * clears it, Escape cancels an edit, Ctrl+Enter (Cmd+Enter) adds a student. Double-click also edits.
 */
export class StudentsListModal extends ExamcModal {
    private readonly table: Api<StudentsListRow>;
    private readonly columnCount: number;
    private readonly errorBox: HTMLElement;
    private readonly saveButton: HTMLButtonElement;

    /** The cell being edited, if any. */
    private editing: { cell: HTMLTableCellElement; input: HTMLInputElement } | null = null;

    public constructor({ title, header, rows, onSave }: StudentsListModalOptions) {
        super(ExamcModal.createElement({
            extraDialogClass: 'modal-xl',
            bodyContent: `
                <div class="modal-body">
                    <div class="alert alert-danger" role="alert" hidden></div>
                    <p class="small text-body-secondary mb-2">
                        Double-click a cell or press Enter to edit it. Ctrl+Enter adds a student.
                    </p>
                    <table class="table table-striped w-100" data-students></table>
                </div>
            `,
            footerContent: `
                <button type="button" class="btn btn-outline-dark btn-sm me-auto" data-add-row>
                    <i class="fa-solid fa-plus" aria-hidden="true"></i> Add student
                </button>
                <button type="button" class="btn btn-dark btn-sm" data-save>Save changes</button>
                <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">Close</button>
            `,
        }));

        this.setTitle(title);
        this.columnCount = header.length;
        this.errorBox = this.element.querySelector<HTMLElement>('.alert')!;
        this.saveButton = this.element.querySelector<HTMLButtonElement>('[data-save]')!;

        const tableElement = this.element.querySelector<HTMLTableElement>('[data-students]')!;

        setupDatatables();
        this.table = new DataTable<StudentsListRow>(tableElement, {
            data: rows,
            columns: buildColumns(header),
            keys: {
                columns: `.${CELL_CLASS}`, // not the delete button column
                clipboard: false, // copy/paste would bypass editing
            },
            order: [], // keep the file's order until the user sorts
            paging: false,
            deferRender: true,
            scrollY: '60vh',
            scrollCollapse: true,
        });

        this.table.on('key', (_event: Event, _dt: unknown, key: number, cell: ApiCellMethods<StudentsListRow>,
            originalEvent: KeyboardEvent) => this.onKey(cell, key, originalEvent));
        tableElement.addEventListener('click', (event) => this.onTableClick(event));
        tableElement.addEventListener('dblclick', (event) => this.onTableDoubleClick(event));

        this.element.querySelector('[data-add-row]')!.addEventListener('click', () => this.addRow());
        this.saveButton.addEventListener('click', () => void this.save(onSave));

        // Ctrl+Enter (Cmd+Enter on macOS) adds a row, even during an edit.
        this.element.addEventListener('keydown', (event) => {
            if (event.key !== 'Enter' || !(event.ctrlKey || event.metaKey)) return;
            event.preventDefault();
            this.addRow();
        });

        // DataTables measures its columns once the table is visible, and the table goes with the dialog.
        this.element.addEventListener('shown.bs.modal', () => this.table.columns.adjust());
        this.element.addEventListener('hidden.bs.modal', () => {
            this.editing = null;
            this.table.destroy();
        });
    }

    /**
     * Shows an error above the table, or hides it.
     *
     * @param {string | null} message - The error, or null to hide it.
     */
    public showError(message: string | null): void {
        this.errorBox.hidden = message === null;
        this.errorBox.textContent = message ?? '';
    }

    /**
     * All rows, in file order (new rows last), whatever the current sorting and search.
     * A cell being edited is saved first.
     *
     * @return {StudentsListRow[]} The rows.
     */
    public rows(): StudentsListRow[] {
        this.commitEdit();
        return this.table.rows({ order: 'index', search: 'none' }).data().toArray() as StudentsListRow[];
    }

    /** Adds an empty row, focuses its first cell and starts editing it. */
    private addRow(): void {
        this.commitEdit();
        const added = this.table.row.add(Array<string>(this.columnCount).fill(''));
        this.table.draw(false);

        const row = added.node() as HTMLTableRowElement | null;
        const firstCell = row?.cells[0];
        if (!row || !firstCell) return;

        row.scrollIntoView({ block: 'nearest' });
        this.startEdit(firstCell);
    }

    private async save(onSave: StudentsListModalOptions['onSave']): Promise<void> {
        const rows = this.rows();
        const label = this.saveButton.textContent;

        this.showError(null);
        this.saveButton.disabled = true;
        this.saveButton.textContent = 'Saving…';

        try {
            await onSave(rows);
            this.hide();
        } catch (error) {
            console.error(error);
            this.showError(error instanceof Error && error.message
                ? error.message
                : 'The students list could not be saved. Please try again.');
        } finally {
            this.saveButton.disabled = false;
            this.saveButton.textContent = label;
        }
    }

    // -----------------------------------------------------------------------
    // Cell editing
    // -----------------------------------------------------------------------

    /**
     * Turns a cell into a text input. KeyTable is disabled meanwhile, so the arrow keys move the caret.
     * Enter or leaving the cell saves, Escape cancels, Tab / Shift+Tab save and let KeyTable move on.
     *
     * @param {HTMLTableCellElement} cell - The cell to edit.
     * @param {string} [initialText] - Text replacing the value (typing on a focused cell), instead of editing it.
     */
    private startEdit(cell: HTMLTableCellElement, initialText?: string): void {
        if (this.editing?.cell === cell || !cell.classList.contains(CELL_CLASS)) return;

        this.commitEdit();
        this.table.cell(cell).focus(); // so Tab moves on from this cell once the edit is saved
        this.table.keys.disable();

        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'form-control form-control-sm';
        input.value = initialText ?? String(this.table.cell(cell).data() ?? '');

        input.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' && !event.ctrlKey && !event.metaKey) {
                event.preventDefault();
                event.stopPropagation(); // KeyTable listens on document: it would start editing again
                this.commitEdit();
            } else if (event.key === 'Escape') {
                event.preventDefault();
                event.stopPropagation(); // keep the dialog open, and KeyTable's focus
                this.cancelEdit();
            } else if (event.key === 'Tab') {
                this.commitEdit(); // KeyTable is enabled again and handles this Tab on document
            }
        });
        input.addEventListener('blur', () => this.commitEdit());

        cell.replaceChildren(input);
        this.editing = { cell, input };
        input.focus();
        if (initialText === undefined) input.select();
    }

    /** Saves the edited cell's value into the table. */
    private commitEdit(): void {
        if (this.editing) this.endEdit(this.editing.cell, this.editing.input.value);
    }

    /** Drops the edited cell's changes. */
    private cancelEdit(): void {
        if (this.editing) this.endEdit(this.editing.cell, null);
    }

    /**
     * Leaves edit mode: KeyTable takes the keyboard back, focus stays on the edited cell.
     *
     * @param {HTMLTableCellElement} cell - The edited cell.
     * @param {string | null} value - The new value, or null to keep the old one.
     */
    private endEdit(cell: HTMLTableCellElement, value: string | null): void {
        this.editing = null; // before data(): re-rendering the cell removes the input, which fires blur
        const cellApi = this.table.cell(cell);
        if (value === null) cellApi.invalidate('data');
        else cellApi.data(value);
        this.table.draw(false);
        this.table.keys.enable();
    }

    // -----------------------------------------------------------------------
    // Events
    // -----------------------------------------------------------------------

    /**
     * Handles keys pressed on the focused cell (KeyTable's `key` event):
     * Enter or F2 edits it, Delete or Backspace clears it, typing replaces its value.
     *
     * @param {ApiCellMethods<StudentsListRow>} cell - The focused cell.
     * @param {number} key - The key code.
     * @param {KeyboardEvent} event - The original key press.
     */
    private onKey(cell: ApiCellMethods<StudentsListRow>, key: number, event: KeyboardEvent): void {
        const node = cell.node() as HTMLTableCellElement | null;
        if (!node || this.editing) return;
        if (event.ctrlKey || event.metaKey || event.altKey) return; // shortcuts, e.g. Ctrl+Enter

        if (key === KEY.enter || key === KEY.f2) {
            event.preventDefault();
            this.startEdit(node);
        } else if (key === KEY.delete || key === KEY.backspace) {
            event.preventDefault();
            cell.data('');
            this.table.draw(false);
        } else if (event.key.length === 1) {
            event.preventDefault(); // the typed character becomes the input's value
            this.startEdit(node, event.key);
        }
    }

    /**
     * Delete buttons remove their row. Other clicks on cells are KeyTable's (focus).
     *
     * @param {MouseEvent} event - The click.
     */
    private onTableClick(event: MouseEvent): void {
        const deleteButton = (event.target as Element).closest(`.${DELETE_BUTTON_CLASS}`);
        if (!deleteButton) return;

        this.commitEdit();
        const row = deleteButton.closest('tr');
        if (row) this.table.row(row).remove().draw(false);
    }

    /**
     * Double-clicking a cell edits it.
     *
     * @param {MouseEvent} event - The double click.
     */
    private onTableDoubleClick(event: MouseEvent): void {
        const cell = (event.target as Element).closest<HTMLTableCellElement>(`td.${CELL_CLASS}`);
        if (cell) this.startEdit(cell);
    }
}