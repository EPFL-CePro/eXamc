import DataTable, { type Api } from 'datatables.net-dt';
import 'datatables.net-dt/css/dataTables.dataTables.css';

import 'datatables.net-columncontrol-dt';
import 'datatables.net-columncontrol-dt/css/columnControl.dataTables.css';

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
            { data: 'copy' },
            { data: 'page' },
            { data: 'mse', render: (v: number | null) => (v == null ? '' : v.toFixed(2)) },
            {
                data: 'sensitivity',
                render: (v: number | null) => (v ? String(v) : '-'),
                createdCell: (cell: HTMLTableCellElement, v: number | null) => {
                    if ((v ?? 0) > 0) {
                        (cell as HTMLTableCellElement).classList.add("sensitive");
                    }
                },
            },
            {
                data: 'timestamp_manual',
                className: 'text-center',
                render: (v: number | null) => (v ? '<i class="fas fa-user-pen fa-sm" style="color: #0d72bf;"></i>' : ''),
            },
            {
                data: 'states',
                className: 'text-center',
                columnControl: [['searchList']],
                render: (states: QuestionState[]) => {
                    const state_labels: Record<QuestionState, string> = { invalid: 'Invalid', empty: 'Empty' };
                    return states
                        .map((s) => `<span class="badge badge-secondary ${s}">${state_labels[s]}</span>`)
                        .join('');
                }
            },
            {
                data: 'page_questions',
                orderable: false,
                width: "60rem",
                columnControl: [['searchList']], // nested array = dropdown; options come from the server
                render: (questions: PageQuestion[] | undefined) => {
                    let html = `<div class="question-badges">`;
                    html += (questions ?? [])
                        .map((q) => {
                            const stateClass = q.state ? ` badge badge-secondary ${q.state}` : '';
                            const title = q.state ? ` title="${q.state}"` : '';
                            const name = DataTable.util.escapeHtml(q.name);
                            return `<span class="badge badge-secondary ${stateClass}"${title}>${name}</span>`;
                        }).join('');
                    html += "</div>";

                    return html;
                }
            },
        ],
        layout: {
            topEnd: "info",
            bottomStart: null,
            bottomEnd: null,
            bottom: "paging"
        },
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