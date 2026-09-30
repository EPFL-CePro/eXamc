import DataTable, { type Api } from 'datatables.net-dt';
import 'datatables.net-dt/css/dataTables.dataTables.css';

import { questionButton, tableElement, typeButton } from './elements.ts';
import { clearPage, loadPage } from './scan.ts';
import { state } from './state.ts';
import type {PageQuestion, PageRow, QuestionFilter, TypeFilter} from './types.ts';

// ---------------------------------------------------------------------------
// Table
// ---------------------------------------------------------------------------

/**
 * Creates the server-side pages table. The type and question filters are sent with every request.
 *
 * @return {Api<unknown>} The DataTables instance (also stored in `state.table`).
 */
export function initTable(): Api<unknown> {
    const apiUrl = tableElement.dataset['apiUrl'];
    if (!apiUrl) throw new Error('#table-copies-pages is missing its data-api-url attribute');

    // TODO - add https://datatables.net/manual/extensions/columncontrol/
    const table = new DataTable(tableElement, {
        serverSide: true,
        processing: true,
        pageLength: 500,
        lengthMenu: [500, 1000, 2000, 3000, 4000],
        ajax: {
            url: apiUrl,
            data: (d) => Object.assign(d, { type: state.typeFilter, question: state.questionFilter.id }),
        },
        columns: [
            { data: 'copy' },
            { data: 'page' },
            {
                data: 'page_questions',
                orderable: false,
                render: (questions: PageQuestion[] | undefined) =>
                    (questions ?? [])
                        .map((q) => {
                            const stateClass = q.state ? ` q-badge-${q.state}` : '';
                            const title = q.state ? ` title="${q.state}"` : '';
                            const name = DataTable.util.escapeHtml(q.name);
                            return `<span class="q-badge${stateClass}"${title}>${name}</span>`;
                        })
                        .join(''),
            },
            { data: 'mse', render: (v: number | null) => (v == null ? '' : v.toFixed(2)) },
            { data: 'sensitivity', render: (v: number | null) => (v ? String(v) : '-') },
            {
                data: 'timestamp_manual',
                className: 'text-center',
                render: (v: number | null, type: string) => {
                    if (type !== 'display') return v ? 1 : 0; // same as data-order
                    return v ? '<i class="fas fa-star fa-sm" style="color: #0d72bf;"></i>' : '';
                },
            },
        ],
        createdRow: function (row: HTMLTableRowElement, data): void {
            const d = data as PageRow;
            row.dataset['copy'] = String(d.copy);
            row.dataset['page'] = String(d.page);
            row.dataset['questions'] = d.questions_ids;
            if ((d.sensitivity ?? 0) > 0 && row.cells[3]) {
                row.cells[3].style.cssText = 'background-color: red; color: black;';
            }
        },
        layout: {
            bottomStart: null,
            bottomEnd: null,
            bottom: "paging",
            bottom1: "info",
            topEnd: null
        },
        scrollY: '70vh',
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

// ---------------------------------------------------------------------------
// Selection
// ---------------------------------------------------------------------------

/**
 * Scrolls the table so the row is vertically centered in its scroll area.
 *
 * @param {HTMLTableRowElement} row - The row to scroll to.
 */
function scrollToRow(row: HTMLTableRowElement): void {
    const container = tableElement.parentElement; // DataTables' scroll body
    if (!container) return;
    container.scrollTop = row.offsetTop - container.clientHeight / 2;
}

/**
 * Highlights a row as the current one and loads its page.
 *
 * @param {HTMLTableRowElement} row - The row to select.
 */
export function selectRow(row: HTMLTableRowElement): void {
    state.currentRow?.classList.remove('is-current');
    row.classList.add('is-current');
    state.currentRow = row;
    void loadPage(row);
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

// ---------------------------------------------------------------------------
// Filters
// ---------------------------------------------------------------------------

/** Shows the current filters on the dropdown buttons. */
export function updateFilterLabels(): void {
    typeButton.textContent = state.typeFilter;
    questionButton.textContent = state.questionFilter.name;
}

/**
 * Applies new filters: reloads the table from the server, then selects the first matching row.
 *
 * @param {TypeFilter} type - The type filter.
 * @param {QuestionFilter} question - The question filter.
 */
export function setFilters(type: TypeFilter, question: QuestionFilter): void {
    state.typeFilter = type;
    state.questionFilter = question;
    updateFilterLabels();

    if (!state.table) return;
    state.table.one('draw', selectFirstRow);
    state.table.ajax.reload();
}