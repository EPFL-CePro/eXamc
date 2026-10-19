import DataTable, { type Api, type ColumnOptions } from 'datatables.net-bs5';
import 'datatables.net-bs5/css';

import { setupDatatables } from '@examc/helpers/datatables.ts';
import { ExamcModal } from '@examc/modals/base.ts';

export interface ReportModalOptions {
    title: string;
    /** Column titles, shown as text. */
    headers: string[];
    /** One row per entry, with one cell per header. */
    rows: HTMLTableRowElement[];
    /** DataTables options of each column; every column is sortable and searchable by default. */
    columns?: ColumnOptions[];
    /** Shown instead of the rows when there are none. */
    emptyMessage?: string;
}

/**
 * A data capture report (missing, unrecognized or overwritten pages), built on the fly and removed once closed.
 * Its rows are paginated by DataTables, and images (with a data-src) are only fetched once their row is shown.
 */
export class ReportModal extends ExamcModal {
    private readonly table: Api<HTMLTableRowElement>;

    public constructor({ title, headers, rows, columns, emptyMessage }: ReportModalOptions) {
        super(ExamcModal.createElement({
            extraDialogClass: 'modal-xl',
            bodyContent: `
                <div class="modal-body">
                    <table class="table table-striped" style="width:100%">
                        <thead><tr></tr></thead>
                    </table>
                </div>
            `,
            footerContent: `<button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">Close</button>`,
        }));

        this.setTitle(title);

        const tableEl = this.element.querySelector('table');
        if (!tableEl) throw new Error('Table element not found for the report modal !');

        setupDatatables();

        // Header texts are set with textContent: never interpreted as HTML.
        tableEl.querySelector('thead tr')!.replaceChildren(...headers.map((text) => {
            const th = document.createElement('th');
            th.textContent = text;
            return th;
        }));

        this.table = new DataTable(tableEl, {
            columns: columns ?? headers.map(() => ({})),
            pageLength: 10,
            lengthMenu: [10, 50, 100, 250],
            scrollY: '69vh',
            order: [], // keep the server's order until the user sorts
            autoWidth: false,
            language: emptyMessage ? { emptyTable: emptyMessage } : {},
            layout: {
                topStart: null, topEnd: null,
                bottomStart: [
                    "pageLength",
                    "info"
                ],
            },
        });

        // Images are only fetched for the rows actually shown.
        this.table.on('draw', () => this.loadShownImages());
        this.table.rows.add(rows).draw();

        // DataTables measures its columns once the table is visible.
        this.element.addEventListener('shown.bs.modal', () => this.table.columns.adjust());
        this.element.addEventListener('hidden.bs.modal', () => this.table.destroy());
    }

    /**
     * Loads the images of the current page's rows. Until then, an image's URL waits in data-src,
     * so the images of other pages are never requested.
     */
    private loadShownImages(): void {
        const rows = this.table.rows({ page: 'current' }).nodes().toArray() as HTMLTableRowElement[];
        for (const row of rows) {
            for (const image of row.querySelectorAll<HTMLImageElement>('img[data-src]')) {
                image.src = image.dataset['src'] ?? '';
                image.removeAttribute('data-src');
            }
        }
    }
}