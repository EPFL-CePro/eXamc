import DataTable, { type Api } from 'datatables.net-bs5';
import 'datatables.net-bs5/css';

import 'datatables.net-buttons-bs5';
import 'datatables.net-select-bs5';

import { icon } from '@examc/helpers/dom.ts';
import { setupDatatables } from '@examc/helpers/datatables.ts';

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
export function columnKeys(rows: StudentRow[]): string[] {
    return rows[0] ? Object.keys(rows[0]).filter((key) => key !== ERROR_KEY) : [];
}

/**
 * Builds the students table in an empty table element, with a checkbox per row.
 *
 * @param {HTMLTableElement} tableElement - The table to fill.
 * @param {StudentRow[]} rows - The students.
 * @return {Api<StudentRow>} The DataTable, to destroy with its dialog.
 */
export function buildSendTable(tableElement: HTMLTableElement, rows: StudentRow[]): Api<StudentRow> {
    const keys = columnKeys(rows);

    const headRow = tableElement.createTHead().insertRow();
    headRow.append(
        document.createElement('th'), // checkbox column
        ...keys.map((key) => {
            const th = document.createElement('th');
            th.textContent = key;
            return th;
        }),
    );

    tableElement.createTBody().append(...rows.map((row) => {
        const tr = document.createElement('tr');
        tr.append(document.createElement('td'), ...keys.map((key) => renderCell(key, row[key] ?? null, row)));
        return tr;
    }));

    setupDatatables();

    return new DataTable<StudentRow>(tableElement, {
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

/**
 * The students selected in the table.
 *
 * @param {Api<StudentRow>} table - The students table.
 * @param {StudentRow[]} rows - Its rows, in table index order.
 * @param {string} emailColumn - The column holding the email address.
 * @return {SelectedStudent[]} The selected students.
 */
export function selectedStudents(table: Api<StudentRow>, rows: StudentRow[], emailColumn: string): SelectedStudent[] {
    const indexes = table.rows({ selected: true }).indexes().toArray() as number[];

    return indexes.flatMap((index) => {
        const row = rows[index];
        if (!row) return [];
        // Assumes the first two data columns are the student id and copy number; adjust if needed.
        const [id = null, copy = null] = columnKeys([row]).map((key) => row[key] ?? null);
        return [{ id, copy, email: row[emailColumn] ?? null }];
    });
}