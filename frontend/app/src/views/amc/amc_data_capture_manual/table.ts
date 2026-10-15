import DataTable, { type Api } from 'datatables.net-bs5';
import 'datatables.net-bs5/css';

import 'datatables.net-columncontrol-bs5';
import 'datatables.net-columncontrol-bs5/css';

import { clearPage, loadPage } from './scan.ts';
import { state } from './state.ts';
import type {PageQuestion, PageRow, QuestionState} from './types.ts';
import {setupDatatables} from "@examc/helpers/datatables.ts";


// ---------------------------------------------------------------------------
// Table
// ---------------------------------------------------------------------------

let tableElement: HTMLTableElement | null = null;


/** Filter-related parts of the last request, to detect when the filters changed. */
let lastFilterKey: string | null = null;

const STATE_LABELS: Record<QuestionState, { label: string; class: string }> = { 
    invalid: { label: 'Invalid', class: "text-bg-danger"},
    empty: { label: 'Empty', class: "text-bg-warning"}
};

/**
 * Serializes the filter-related request parameters (global search, type, ColumnControl selections).
 * Paging and ordering are left out, so moving between pages doesn't count as a filter change.
 *
 * @param {Record<string, unknown>} params - The parameters of an Ajax request.
 * @return {string} A key that changes only when the filters change.
 */
function filterKey(params: Record<string, unknown>): string {
    const columns = (params['columns'] as { columnControl?: unknown }[] | undefined) ?? [];
    return JSON.stringify([params['search'], params['type'], columns.map((c) => c.columnControl)]);
}

/**
 * Creates the server-side pages table. The type filter is sent with every request;
 * the question filter is the questions column's ColumnControl list.
 *
 * @return {Api<unknown>} The DataTables instance (also stored in `state.table`).
 */
export function initTable(element: HTMLTableElement): Api<unknown> {
    tableElement = element;

    const apiUrl = tableElement.dataset['apiUrl'];
    if (!apiUrl) throw new Error('#table-copies-pages is missing its data-api-url attribute');

    setupDatatables();

    const table = new DataTable(tableElement, {
        serverSide: true,
        processing: true,
        pageLength: 500,
        lengthMenu: [500, 1000, 2000, 3000, 4000],
        columnControl: ['info', 'order'],
        ordering: {
            indicators: false,
            handler: false
        },
        ajax: apiUrl,
                columns: [
            { data: 'copy', className: 'text-nowrap', width: '1%' },
            { data: 'page', className: 'text-nowrap', width: '1%' },
            { data: 'mse', className: 'text-nowrap', width: '1%', render: (v: number | null) => (v == null ? '' : v.toFixed(2)) },
            {
                data: 'sensitivity',
                className: 'text-nowrap',
                width: '1%',
                render: (v: number | null) => (v ? String(v) : '-'),
                createdCell: (cell: HTMLTableCellElement, v: number | null) => {
                    if ((v ?? 0) > 0) cell.classList.add('text-danger');
                },
            },
            {
                data: 'timestamp_manual',
                className: 'text-center text-nowrap',
                width: '1%',
                render: (v: number | null) => (v ? '<i class="fa-solid fa-user-pen fa-sm text-primary"></i>' : ''),
            },
            {
                data: 'states',
                className: 'text-nowrap',
                width: '1%',
                columnControl: [['searchList']],
                render: (states: QuestionState[]) => states
                    .map((s) => `<span class="badge rounded-pill ${STATE_LABELS[s].class}">${STATE_LABELS[s].label}</span>`)
                    .join(' '),
            },
            {
                data: 'page_questions',
                orderable: false,
                // No width class: it gets whatever the other columns leave
                columnControl: [['searchList']],
                render: (questions: PageQuestion[] | undefined) => {
                    const badges = (questions ?? []).map((q) => {
                        const stateClass = q.state ? STATE_LABELS[q.state].class : 'text-bg-light';
                        const title = q.state ? ` title="${q.state}"` : '';
                        const name = DataTable.util.escapeHtml(q.name);
                        return `<span class="badge rounded-pill ${stateClass}"${title}>${name}</span>`;
                    });
                    return `<div class="d-flex flex-wrap gap-2">${badges.join('')}</div>`;
                },
            },
        ],
        layout: {
            topEnd: "info",
            bottomStart: null,
            bottomEnd: null,
            bottom: "paging"
        },
        scrollX: true,
        scrollY: '79vh',
    });

    // On the initial load and after any filter change (question list, type, search): select the first row.
    table.on('draw', () => {
        const key = filterKey(table.ajax.params() as Record<string, unknown>);
        if (key === lastFilterKey) return;
        lastFilterKey = key;
        selectFirstRow();
    });

    state.table = table;
    return table;
}

/**
 * Rows of the currently displayed table page, in display order (already filtered by the server).
 *
 * @return {HTMLTableRowElement[]} The rows.
 */
function pageRows(): HTMLTableRowElement[] {
    if (!state.table) return [];
    return state.table.rows({ page: 'current' }).nodes().toArray() as HTMLTableRowElement[];
}

/**
 * The API data behind a table row, or undefined for non-data rows ("No data", "Processing").
 *
 * @param {HTMLTableRowElement} row - A row of the table.
 * @return {PageRow | undefined} Its data.
 */
function rowData(row: HTMLTableRowElement): PageRow | undefined {
    return state.table?.row(row).data() as PageRow | undefined;
}

// ---------------------------------------------------------------------------
// Selection
// ---------------------------------------------------------------------------

/**
 * Scrolls the table so the row is vertically centered in its scroll area.
 *
 * @param {HTMLTableRowElement} row - The row to scroll to.
 */
function scrollToRow(row: HTMLTableRowElement): void {
    const container = tableElement?.parentElement; // DataTables' scroll body
    if (!container) return;
    container.scrollTop = row.offsetTop - container.clientHeight / 2;
}

/**
 * Highlights a row as the current one and loads its page. Rows without data are ignored.
 *
 * @param {HTMLTableRowElement} row - The row to select.
 */
export function selectRow(row: HTMLTableRowElement): void {
    const data = rowData(row);
    if (!data) return;

    state.currentRow?.classList.remove('is-current');
    row.classList.add('is-current');
    state.currentRow = row;
    loadPage(data);
}

/** Selects the first row of the current table page, or shows the placeholder if there is none. */
export function selectFirstRow(): void {
    const first = pageRows()[0];
    if (first) {
        selectRow(first);
        return;
    }
    state.currentRow = null;
    clearPage();
}

/**
 * Selects the next/previous row, moving to the next/previous table page at the edges.
 *
 * @param {1 | -1} step - 1 for next, -1 for previous.
 */
export function navigate(step: 1 | -1): void {
    const { table } = state;
    if (!table) return;
    const rows = pageRows();
    if (rows.length === 0) return;

    const index = state.currentRow ? rows.indexOf(state.currentRow) : -1;
    const target = index === -1 ? rows[0] : rows[index + step];

    if (target) {
        selectRow(target);
        scrollToRow(target);
        return;
    }

    // Past the first/last row: load the previous/next page, then select its last/first row.
    const { page, pages } = table.page.info();
    const nextPage = page + step;
    if (nextPage < 0 || nextPage >= pages) return;

    table.one('draw', () => {
        const newRows = pageRows();
        const row = step === 1 ? newRows[0] : newRows[newRows.length - 1];
        if (row) {
            selectRow(row);
            scrollToRow(row);
        }
    });
    table.page(nextPage).draw('page');
}