import DataTable from 'datatables.net-dt';
import 'datatables.net-dt/css/dataTables.dataTables.css';

import 'datatables.net-buttons-dt';
import 'datatables.net-select-dt';

import { byId, icon } from '@examc/helpers/dom.ts';
import { setupDatatables } from '@examc/helpers/datatables.ts';
import { state } from './state.ts';
import type { CellValue, SelectedStudent, StudentRow } from './types.ts';

/** Column sent by the server for the status tooltip; not displayed as a column. */
const ERROR_KEY = 'error';

/**
 * Renders one cell: dates as local time, status as an icon, anything else as text.
 *
 * @param {string} key - The column name.
 * @param {CellValue} value - The cell value.
 * @param {StudentRow} row - The whole row (for the status error message).
 * @return {HTMLTableCellElement} The cell.
 */
function renderCell(key: string, value: CellValue, row: StudentRow): HTMLTableCellElement {
    const td = document.createElement('td');

    if (key.includes('date')) {
        td.textContent = typeof value === 'number' ? new Date(value * 1000).toLocaleString() : '';
    } else if (key === 'status') {
        if (value === 1) {
            td.append(icon('fa-solid fa-thumbs-up fa-l', 'green'));
        } else if (value !== 0) {
            td.append(icon('fa-solid fa-triangle-exclamation fa-l', 'red', String(row[ERROR_KEY] ?? '')));
        }
    } else {
        td.textContent = value === null ? '' : String(value);
    }

    return td;
}

/**
 * Column names of the rows, without the error column.
 *
 * @param {StudentRow[]} rows - The rows.
 * @return {string[]} The displayed column names.
 */
function columnKeys(rows: StudentRow[]): string[] {
    return rows[0] ? Object.keys(rows[0]).filter((key) => key !== ERROR_KEY) : [];
}

/**
 * (Re)builds the students table of the send dialog. An existing table is destroyed first,
 * so reopening the dialog shows the latest send statuses.
 *
 * @param {StudentRow[]} rows - The students.
 */
export function buildSendTable(rows: StudentRow[]): void {
    const tableElement = byId<HTMLTableElement>('send-annotated-papers-table');

    state.sendTable?.destroy();
    state.sendTable = null;
    state.sendRows = rows;

    const keys = columnKeys(rows);

    byId('send-annotated-papers-table-thead').replaceChildren(
        document.createElement('th'), // checkbox column
        ...keys.map((key) => {
            const th = document.createElement('th');
            th.textContent = key;
            return th;
        }),
    );

    byId('send-annotated-papers-table-tbody').replaceChildren(
        ...rows.map((row) => {
            const tr = document.createElement('tr');
            tr.append(document.createElement('td'), ...keys.map((key) => renderCell(key, row[key] ?? null, row)));
            return tr;
        }),
    );

    setupDatatables();

    state.sendTable = new DataTable<StudentRow>(tableElement, {
        scrollY: '25vh',
        paging: false,
        select: {
            style: 'multi',
            selector: 'td',
            items: 'row',
        },
        columnDefs: [
            {
                targets: 0,
                orderable: false,
                searchable: false,
                render: DataTable.render.select(), // renders the checkbox
            },
        ],
        layout: {
            topEnd: 'search',
            bottomStart: 'info',
            bottomEnd: null,
        },
    });
}

/** Recalculates column widths; needed once the table is visible, since it was built while hidden. */
export function adjustSendTable(): void {
    state.sendTable?.columns.adjust();
}

/**
 * The students selected in the table.
 *
 * @param {string} emailColumn - The column holding the email address.
 * @return {SelectedStudent[]} The selected students.
 */
export function selectedStudents(emailColumn: string): SelectedStudent[] {
    if (!state.sendTable) return [];
    const indexes = state.sendTable.rows({ selected: true }).indexes().toArray() as number[];

    return indexes.flatMap((index) => {
        const row = state.sendRows[index];
        if (!row) return [];
        // Assumes the first two data columns are the student id and copy number; adjust if needed.
        const [id = null, copy = null] = columnKeys([row]).map((key) => row[key] ?? null);
        return [{ id, copy, email: row[emailColumn] ?? null }];
    });
}