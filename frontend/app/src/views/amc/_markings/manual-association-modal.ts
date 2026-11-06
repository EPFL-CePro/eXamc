import DataTable, { type Api } from 'datatables.net-bs5';
import 'datatables.net-bs5/css';

import { setupDatatables } from '@examc/helpers/datatables.ts';
import { ExamcModal } from '@examc/modals/base.ts';


/** The manual association dialog, built on the fly and removed once closed. Its rows are paginated by DataTables. */
export class ManualAssociationModal extends ExamcModal {
    private readonly table: Api<HTMLTableRowElement>;
    private readonly errorBox: HTMLElement;

    /**
     * @param {() => void} onClosed - Called once the dialog is closed, before its table is destroyed.
     */
    public constructor(onClosed: () => void) {
        super(ExamcModal.createElement({
            extraDialogClass: 'modal-xl',
            bodyContent: `
                <div class="modal-body">
                    <div class="alert alert-danger" role="alert" hidden></div>
                    <table id="manual-association-table" class="table table-striped" style="width:100%">
                        <thead>
                            <tr>
                                <th>Copy</th>
                                <th>Automatic</th>
                                <th>Manual</th>
                                <th>Associated</th>
                                <th>SCIPER image</th>
                                <th>Student</th>
                            </tr>
                        </thead>
                    </table>
                </div>
            `,
            footerContent: `<button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">Close</button>`,
        }));

        this.setTitle('Manual association');
        this.errorBox = this.element.querySelector('.alert')!;

        setupDatatables();
        const tableEl = this.element.querySelector('table');
        if (!tableEl) throw new Error("Table element not found for the manual association modal !");

        this.table = new DataTable(tableEl, {
            columns: [
                {},
                {},
                {},
                { orderSequence: ['desc', 'asc'] }, // first click: "Not associated" sheets first
                { orderable: false, searchable: false }, // the scan image
                { orderable: false }, // the student picker
            ],
            pageLength: 10,
            lengthMenu: [10, 50, 100, 250],
            scrollY: "69vh",
            order: [], // keep the server's order until the user sorts
            autoWidth: false,
        });

        // Scan images are only fetched for the rows actually shown.
        this.table.on('draw', () => this.loadShownImages());

        // DataTables measures its columns once the table is visible.
        this.element.addEventListener('shown.bs.modal', () => this.table.columns.adjust());
        this.element.addEventListener('hidden.bs.modal', () => {
            onClosed();
            this.table.destroy();
        });
    }

    /**
     * Loads the scan images of the current page's rows. Until then, an image's URL waits in data-src,
     * so the images of other pages are never requested.
     */
    private loadShownImages(): void {
        const rows = this.table.rows({ page: 'current' }).nodes().toArray() as HTMLTableRowElement[];
        for (const row of rows) {
            for (const image of row.querySelectorAll<HTMLImageElement>('img[data-src]')) {
                image.src = image.dataset['src'] ?? '';
                image.style.maxWidth = "20rem";
                image.removeAttribute('data-src');
            }
        }
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
     * Replaces the rows, keeping the current page, sorting and search.
     *
     * @param {HTMLTableRowElement[]} rows - One row per answer sheet.
     */
    public setRows(rows: HTMLTableRowElement[]): void {
        this.table.clear();
        this.table.rows.add(rows);
        this.table.draw(false);
    }

    /**
     * All rows, including those of other pages (DataTables only keeps the current page in the page).
     *
     * @return {HTMLTableRowElement[]} The rows.
     */
    public rowNodes(): HTMLTableRowElement[] {
        return this.table.rows().nodes().toArray() as HTMLTableRowElement[];
    }

    /**
     * Goes to the page holding a row, with the current sorting and search.
     *
     * @param {HTMLTableRowElement} row - A row of the table.
     */
    public showRow(row: HTMLTableRowElement): void {
        const shown = this.table.rows({ order: 'current', search: 'applied' }).nodes().toArray() as HTMLTableRowElement[];
        const index = shown.indexOf(row);
        if (index >= 0) this.table.page(Math.floor(index / this.table.page.len())).draw(false);
    }
}