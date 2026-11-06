import DataTable, { type Api } from 'datatables.net-bs5';
import 'datatables.net-bs5/css';
import 'datatables.net-columncontrol-bs5';
import 'datatables.net-columncontrol-bs5/css';

import { setupDatatables } from '@examc/helpers/datatables.ts';
import { requireData } from '@examc/helpers/dom.ts';

import { clearPage, loadPage } from './scan.ts';
import type { PageQuestion, PageRow, QuestionState } from './types.ts';

const PAGE_LENGTH = 500;

const STATE_LABELS: Record<QuestionState, { label: string; class: string }> = {
    invalid: { label: 'Invalid', class: 'text-bg-danger' },
    empty: { label: 'Empty', class: 'text-bg-warning' },
};

/** A copy/page from the URL, and its position in the default (unfiltered) list. */
export interface InitialPosition {
    copy: string;
    page: string;
    index: number;
}

let table: Api<unknown> | null = null;
let currentRow: HTMLTableRowElement | null = null;
/** Row to select after the first draw (from the URL). */
let pendingInitial: InitialPosition | null = null;
/** Filter-related parts of the last request, to detect when the filters changed. */
let lastFilterKey: string | null = null;

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

/** Badge for a flagged state; green once the page was checked manually. */
function stateBadge(state: QuestionState, text: string, checked: boolean): string {
    const { label, class: cls } = STATE_LABELS[state];
    if (!checked) return `<span class="badge rounded-pill ${cls}" title="${label}">${text}</span>`;
    return '<span class="badge rounded-pill bg-success-subtle text-success-emphasis border border-success-subtle"'
        + ` title="${label}, checked manually"><i class="fa-solid fa-check fa-xs"></i> ${text}</span>`;
}

function renderStates(states: QuestionState[], _type: string, row: PageRow): string {
    return states.map((s) => stateBadge(s, STATE_LABELS[s].label, !!row.timestamp_manual)).join(' ');
}

function renderQuestions(questions: PageQuestion[] | undefined, _type: string, row: PageRow): string {
    const badges = (questions ?? []).map((q) => {
        const name = DataTable.util.escapeHtml(q.name);
        return q.state
            ? stateBadge(q.state, name, !!row.timestamp_manual)
            : `<span class="badge rounded-pill text-bg-light">${name}</span>`;
    });
    return `<div class="d-flex flex-wrap gap-2">${badges.join('')}</div>`;
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

/**
 * Reads ?copy=&page= from the URL and asks the API where that row is.
 *
 * @param {string} locateUrl - The locate endpoint.
 * @return {Promise<InitialPosition | undefined>} The position; undefined if absent or not found.
 */
export async function initialPosition(locateUrl: string): Promise<InitialPosition | undefined> {
    const params = new URLSearchParams(location.search);
    const copy = params.get('copy');
    const page = params.get('page');
    if (!copy || !page) return undefined;

    const url = new URL(locateUrl, location.origin);
    url.search = new URLSearchParams({ copy, page }).toString();
    try {
        const response = await fetch(url, { credentials: 'same-origin' });
        if (!response.ok) return undefined;
        const { index } = (await response.json()) as { index: number };
        return { copy, page, index };
    } catch {
        return undefined;
    }
}

/** Realigns the header with the body after the table's width changed. */
export function adjustColumns(): void {
    table?.columns.adjust();
}

/**
 * Creates the server-side pages table and selects the URL's row, or the first one.
 *
 * @param {HTMLTableElement} element - The table (with data-api-url).
 * @param {InitialPosition} initial - Row to open on, if any.
 */
export function initTable(element: HTMLTableElement, initial?: InitialPosition): void {
    pendingInitial = initial ?? null;
    setupDatatables();

    table = new DataTable(element, {
        serverSide: true,
        processing: true,
        ajax: requireData(element, 'apiUrl'),
        pageLength: PAGE_LENGTH,
        lengthMenu: [500, 1000, 2000, 3000, 4000],
        order: [[0, 'asc']], // keep in sync with the locate endpoint
        displayStart: initial ? Math.floor(initial.index / PAGE_LENGTH) * PAGE_LENGTH : 0,
        columnControl: ['info', 'order'],
        ordering: { indicators: false, handler: false },
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
            { data: 'states', className: 'text-nowrap', width: '1%', columnControl: [['searchList']], render: renderStates },
            { data: 'page_questions', orderable: false, columnControl: [['searchList']], render: renderQuestions },
        ],
        layout: { topEnd: 'info', bottomStart: null, bottomEnd: null, bottom: 'paging' },
        scrollX: true,
        scrollY: '73vh',
    });

    table.on('draw', onDraw);

    element.tBodies[0]?.addEventListener('click', (event) => {
        const row = (event.target as Element).closest('tr');
        if (row && rowData(row)) select(row);
    });
}

/** First draw and filter changes: select the URL's row, or the first one. Paging is handled by navigate(). */
function onDraw(): void {
    if (!table) return;
    const params = table.ajax.params() as Record<string, unknown>;
    const columns = (params['columns'] as { columnControl?: unknown }[] | undefined) ?? [];
    const key = JSON.stringify([params['search'], columns.map((c) => c.columnControl)]);
    if (key === lastFilterKey) return;
    lastFilterKey = key;

    const initial = pendingInitial;
    pendingInitial = null;
    const rows = pageRows();
    const match = initial && rows.find((r) => {
        const data = rowData(r);
        return data && String(data.copy) === initial.copy && String(data.page) === initial.page;
    });

    if (match) select(match, true);
    else if (rows[0] && rowData(rows[0])) select(rows[0]);
    else {
        currentRow = null;
        clearPage();
    }
}

// ---------------------------------------------------------------------------
// Rows
// ---------------------------------------------------------------------------

function pageRows(): HTMLTableRowElement[] {
    return (table?.rows({ page: 'current' }).nodes().toArray() ?? []) as HTMLTableRowElement[];
}

/** The API data behind a row; undefined for "No data" / "Processing" rows. */
function rowData(row: HTMLTableRowElement): PageRow | undefined {
    return table?.row(row).data() as PageRow | undefined;
}

/**
 * Highlights a row, loads its page and puts its copy/page in the URL.
 *
 * @param {HTMLTableRowElement} row - A data row.
 * @param {boolean} scroll - Whether to scroll it to the middle of the table.
 */
function select(row: HTMLTableRowElement, scroll = false): void {
    const data = rowData(row);
    if (!data) return;

    currentRow?.classList.remove('table-active');
    row.classList.add('table-active');
    currentRow = row;
    void loadPage(data);

    if (scroll) {
        const body = row.closest<HTMLElement>('.dt-scroll-body');
        if (body) body.scrollTop = row.offsetTop - body.clientHeight / 2;
    }

    const url = new URL(location.href);
    url.searchParams.set('copy', String(data.copy));
    url.searchParams.set('page', String(data.page));
    history.replaceState(null, '', url);
}

/**
 * Selects the next/previous row, moving to the next/previous table page at the edges.
 *
 * @param {1 | -1} step - 1 for next, -1 for previous.
 */
export function navigate(step: 1 | -1): void {
    if (!table) return;
    const rows = pageRows().filter((r) => rowData(r));
    if (rows.length === 0) return;

    const index = currentRow ? rows.indexOf(currentRow) : -1;
    const target = index === -1 ? rows[0] : rows[index + step];
    if (target) {
        select(target, true);
        return;
    }

    const { page, pages } = table.page.info();
    const nextPage = page + step;
    if (nextPage < 0 || nextPage >= pages) return;

    table.one('draw', () => {
        const newRows = pageRows();
        const row = step === 1 ? newRows[0] : newRows[newRows.length - 1];
        if (row) select(row, true);
    });
    table.page(nextPage).draw('page');
}

/** Marks the current row as manually edited and re-renders it (its badges turn green). */
export function markCurrentRowEdited(): void {
    if (!table || !currentRow) return;
    const row = table.row(currentRow);
    const data = row.data() as PageRow | undefined;
    if (!data) return;
    data.timestamp_manual = Math.floor(Date.now() / 1000);
    row.invalidate('data'); // re-renders the cells; the row node and its highlight are kept
}
