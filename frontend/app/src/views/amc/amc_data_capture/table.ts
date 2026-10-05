import DataTable, { type Api } from 'datatables.net-dt';

import 'datatables.net-columncontrol-dt';
import 'datatables.net-columncontrol-dt/css/columnControl.dataTables.css';

import { openZooms } from './zooms.ts';
import type { DiagnosisRow, PagePosition } from './types.ts';
import {setupDatatables} from "@examc/helpers/datatables.ts";

let table: Api<unknown> | null = null;
let currentRow: HTMLTableRowElement | null = null;

/**
 * Creates the diagnosis table from the manual data capture API
 *
 * @param {HTMLTableElement} tableElement - The table, with a data-api-url attribute.
 */
export function initDiagnosis(tableElement: HTMLTableElement): void {
    const apiUrl = tableElement.dataset['apiUrl'];
    if (!apiUrl) throw new Error('#table-copies-pages is missing its data-api-url attribute');

    setupDatatables();

    const dataTable = new DataTable(tableElement, {
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
                createdCell: (cell, v: number | null) => {
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
                data: null,
                orderable: false,
                searchable: false,
                className: 'text-center',
                defaultContent:
                    '<span data-action="zooms" aria-label="Show box zooms" style="cursor: pointer">' +
                        '<i class="far fa-eye fa-lg"></i>' +
                    '</span>'
            },
        ],
        layout: {
            topStart: function() {
                const title = document.createElement('h6');
                title.style.margin = "0";
                title.innerHTML = `<i class="fa-solid fa-stethoscope"></i> Diagnosis`;

                return title;
            },
            topEnd: "pageLength",
            bottomStart: 'info',
            bottomEnd: 'paging',
        },
        autoWidth: true,
        scrollY: '51vh',
    });

    table = dataTable;

    // Row click highlights it; the eye button also opens its zooms.
    tableElement.addEventListener('click', (event) => {
        const target = event.target as Element;
        const row = target.closest('tbody tr');
        if (!(row instanceof HTMLTableRowElement) || !rowData(row)) return;

        highlight(row);
        if (target.closest('[data-action="zooms"]')) openRowZooms(row);
    });

    // Highlight the first row once the data has arrived.
    dataTable.one('draw', () => {
        const first = pageRows()[0];
        if (first) highlight(first);
    });

    // The table lives in a tab that may be hidden when it's created: fix the column widths once it's shown.
    const container = tableElement.closest('.dt-container') ?? tableElement.parentElement;
    if (container) {
        let lastWidth = 0;
        new ResizeObserver(([entry]) => {
            const width = entry?.contentRect.width ?? 0;
            if (width > 0 && width !== lastWidth) {
                lastWidth = width;
                dataTable.columns.adjust();
            }
        }).observe(container);
    }
}

function pageRows(): HTMLTableRowElement[] {
    if (!table) return [];
    return table.rows({ page: 'current' }).nodes().toArray() as HTMLTableRowElement[];
}

function rowData(row: HTMLTableRowElement): DiagnosisRow | undefined {
    return table?.row(row).data() as DiagnosisRow | undefined;
}

function toPosition(row: DiagnosisRow): PagePosition {
    return { copy: String(row.copy), page: String(row.page) };
}

function highlight(row: HTMLTableRowElement): void {
    currentRow?.classList.remove('is-current');
    row.classList.add('is-current');
    currentRow = row;
}

function openRowZooms(row: HTMLTableRowElement): void {
    const data = rowData(row);
    if (!data) return;
    highlight(row);
    row.scrollIntoView({ block: 'nearest' });
    void openZooms(toPosition(data));
}

/**
 * Opens the zooms of the previous/next row, moving to the previous/next table page at the edges.
 *
 * @param {1 | -1} step - 1 for next, -1 for previous.
 */
export function navigateZooms(step: 1 | -1): void {
    const dataTable = table;
    if (!dataTable || !currentRow) return;

    const rows = pageRows();
    const index = rows.indexOf(currentRow);
    const target = index === -1 ? undefined : rows[index + step];
    if (target) {
        openRowZooms(target);
        return;
    }

    const { page, pages } = dataTable.page.info();
    const nextPage = page + step;
    if (index === -1 || nextPage < 0 || nextPage >= pages) return;

    dataTable.one('draw', () => {
        const newRows = pageRows();
        const row = step === 1 ? newRows[0] : newRows[newRows.length - 1];
        if (row) openRowZooms(row);
    });
    dataTable.page(nextPage).draw('page');
}
