import DataTable, { type Api, type ApiCellMethods, type ColumnOptions } from 'datatables.net-dt';
import 'datatables.net-dt/css/dataTables.dataTables.css';
import 'datatables.net-keytable-dt';
import 'datatables.net-keytable-dt/css';

import { byId } from '@examc/helpers/dom.ts';
import { setupDatatables } from '@examc/helpers/datatables.ts';
import { state } from '../state.ts';
import type { StudentsListRow } from '../types.ts';

/** Class of the CSV columns: the only ones KeyTable can focus. */
const CELL_CLASS = 'students-list-cell';
const DELETE_BUTTON_CLASS = 'students-list-delete';

/** Key codes KeyTable passes to the `key` event. */
const KEY = { backspace: 8, enter: 13, delete: 46, f2: 113 } as const;

/** Number of CSV columns; the delete button column comes after them. */
let dataColumns = 0;

/** The cell being edited, if any. */
let editing: { cell: HTMLTableCellElement; input: HTMLInputElement } | null = null;

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
            + 'title="Delete row"><i class="fas fa-trash"></i></button>',
    });

    return columns;
}

/**
 * Leaves edit mode: KeyTable takes the keyboard back, focus stays on the edited cell.
 *
 * @param {Api<StudentsListRow>} table - The table.
 * @param {HTMLTableCellElement} cell - The edited cell.
 * @param {string | null} value - The new value, or null to keep the old one.
 */
function endEdit(table: Api<StudentsListRow>, cell: HTMLTableCellElement, value: string | null): void {
    editing = null; // before data(): re-rendering the cell removes the input, which fires blur
    const cellApi = table.cell(cell);
    if (value === null) cellApi.invalidate('data');
    else cellApi.data(value);
    table.draw(false);
    table.keys.enable();
}

/** Saves the edited cell's value into the table. */
function commitEdit(): void {
    if (!editing || !state.studentsTable) return;
    endEdit(state.studentsTable, editing.cell, editing.input.value);
}

/** Drops the edited cell's changes. */
function cancelEdit(): void {
    if (!editing || !state.studentsTable) return;
    endEdit(state.studentsTable, editing.cell, null);
}

/**
 * Turns a cell into a text input. KeyTable is disabled meanwhile, so the arrow keys move the caret.
 * Enter or leaving the cell saves, Escape cancels, Tab / Shift+Tab save and let KeyTable move on.
 *
 * @param {HTMLTableCellElement} cell - The cell to edit.
 * @param {string} [initialText] - Text replacing the value (typing on a focused cell), instead of editing it.
 */
function startEdit(cell: HTMLTableCellElement, initialText?: string): void {
    const table = state.studentsTable;
    if (!table || editing?.cell === cell || !cell.classList.contains(CELL_CLASS)) return;

    commitEdit();
    table.cell(cell).focus(); // so Tab moves on from this cell once the edit is saved
    table.keys.disable();

    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'form-control form-control-sm';
    input.value = initialText ?? String(table.cell(cell).data() ?? '');

    input.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && !event.ctrlKey && !event.metaKey) {
            event.preventDefault();
            event.stopPropagation(); // KeyTable listens on document: it would start editing again
            commitEdit();
        } else if (event.key === 'Escape') {
            event.preventDefault();
            event.stopPropagation(); // keep the modal open, and KeyTable's focus
            cancelEdit();
        } else if (event.key === 'Tab') {
            commitEdit(); // KeyTable is enabled again and handles this Tab on document
        }
    });
    input.addEventListener('blur', () => commitEdit());

    cell.replaceChildren(input);
    editing = { cell, input };
    input.focus();
    if (initialText === undefined) input.select();
}

/**
 * Handles keys pressed on the focused cell (KeyTable's `key` event):
 * Enter or F2 edits it, Delete or Backspace clears it, typing replaces its value.
 *
 * @param {ApiCellMethods<StudentsListRow>} cell - The focused cell.
 * @param {number} key - The key code.
 * @param {KeyboardEvent} event - The original key press.
 */
function onKey(cell: ApiCellMethods<StudentsListRow>, key: number, event: KeyboardEvent): void {
    const table = state.studentsTable;
    const node = cell.node() as HTMLTableCellElement | null;
    if (!table || !node || editing) return;

    if (key === KEY.enter || key === KEY.f2) {
        event.preventDefault();
        startEdit(node);
    } else if (key === KEY.delete || key === KEY.backspace) {
        event.preventDefault();
        cell.data('');
        table.draw(false);
    } else if (event.key.length === 1) {
        event.preventDefault(); // the typed character becomes the input's value
        startEdit(node, event.key);
    }
}

/**
 * Ctrl+Enter (Cmd+Enter on macOS) adds a row while the dialog is open, even during an edit.
 *
 * @param {KeyboardEvent} event - The key press.
 */
function onDocumentKeydown(event: KeyboardEvent): void {
    if (event.key !== 'Enter' || !(event.ctrlKey || event.metaKey)) return;

    const container = document.getElementById('students-list-table-container');
    if (!state.studentsTable || !container || container.offsetParent === null) return; // dialog hidden

    event.preventDefault();
    addStudentsTableRow();
}

/**
 * Handles clicks in the table: delete buttons remove their row. Clicks on cells are KeyTable's (focus).
 *
 * @param {MouseEvent} event - The click.
 */
function onTableClick(event: MouseEvent): void {
    const table = state.studentsTable;
    const deleteButton = (event.target as Element).closest(`.${DELETE_BUTTON_CLASS}`);
    if (!table || !deleteButton) return;

    commitEdit();
    const row = deleteButton.closest('tr');
    if (row) table.row(row).remove().draw(false);
}

/**
 * Double-clicking a cell edits it.
 *
 * @param {MouseEvent} event - The double click.
 */
function onTableDoubleClick(event: MouseEvent): void {
    const cell = (event.target as Element).closest<HTMLTableCellElement>(`td.${CELL_CLASS}`);
    if (cell) startEdit(cell);
}

/** Destroys the table and removes it from the page. */
export function destroyStudentsTable(): void {
    editing = null;
    document.removeEventListener('keydown', onDocumentKeydown);
    state.studentsTable?.destroy(true);
    state.studentsTable = null;
}

/**
 * Builds the editable students table in its container, replacing any previous one.
 *
 * @param {string[]} header - The CSV header.
 * @param {StudentsListRow[]} rows - The rows.
 */
export function buildStudentsTable(header: string[], rows: StudentsListRow[]): void {
    destroyStudentsTable();
    dataColumns = header.length;

    const tableElement = document.createElement('table');
    tableElement.className = 'display compact';
    tableElement.style.width = '100%';
    tableElement.addEventListener('click', onTableClick);
    tableElement.addEventListener('dblclick', onTableDoubleClick);
    byId('students-list-table-container').replaceChildren(tableElement);

    setupDatatables();

    const table = new DataTable<StudentsListRow>(tableElement, {
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

    table.on('key', (_event: Event, _dt: unknown, key: number, cell: ApiCellMethods<StudentsListRow>,
        originalEvent: KeyboardEvent) => onKey(cell, key, originalEvent));

    // Ctrl+Enter shortcut to add a new row
    document.addEventListener('keydown', onDocumentKeydown);

    state.studentsTable = table;
}

/** Recalculates column widths; needed once the dialog is visible, since the table was built while hidden. */
export function adjustStudentsTable(): void {
    state.studentsTable?.columns.adjust();
}

/** Adds an empty row, focuses its first cell and starts editing it. */
export function addStudentsTableRow(): void {
    const table = state.studentsTable;
    if (!table) return;

    commitEdit();
    const added = table.row.add(Array<string>(dataColumns).fill(''));
    table.draw(false);

    const row = added.node() as HTMLTableRowElement | null;
    const firstCell = row?.cells[0];
    if (!row || !firstCell) return;

    row.scrollIntoView({ block: 'nearest' });
    startEdit(firstCell);
}

/**
 * All rows, in file order (new rows last), whatever the current sorting and search.
 *
 * @return {StudentsListRow[]} The rows.
 */
export function studentsTableRows(): StudentsListRow[] {
    commitEdit();
    if (!state.studentsTable) return [];
    return state.studentsTable.rows({ order: 'index', search: 'none' }).data().toArray() as StudentsListRow[];
}