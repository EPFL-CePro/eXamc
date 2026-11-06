import { byId } from '@examc/helpers/dom.ts';
import { parseJson, postForm, postText, toScanUrl } from '@examc/helpers/http.ts';
import { LoadingModal } from '@examc/modals/loading.ts';
import { LocalModal } from '@examc/modals/local.ts';

import { ReportModal } from './report-modal.ts';
import type { MissingPagesCopy, OverwrittenPage, UnrecognizedPage } from './types.ts';

interface ReportsConfig {
    unrecognizedUrl: string;
    missingPages: MissingPagesCopy[];
    overwrittenPages: OverwrittenPage[];
}

const TITLES = {
    missing: 'Missing pages',
    unrecognized: 'Unrecognized pages',
    overwritten: 'Overwritten pages',
};
type ReportKind = keyof typeof TITLES;

/** Columns holding an image or a button: neither sorted nor searched. */
const STATIC_COLUMN = { orderable: false, searchable: false };

/** Builds a table row; strings are added as text, never as HTML. */
function tableRow(cells: (string | Node)[]): HTMLTableRowElement {
    const tr = document.createElement('tr');
    for (const cell of cells) {
        const td = document.createElement('td');
        td.append(cell);
        tr.append(td);
    }
    return tr;
}

/** Shown instead of a scan whose file can't be loaded. */
function missingScanNotice(): HTMLElement {
    const notice = document.createElement('span');
    notice.className = 'text-danger';
    notice.innerHTML = '<i class="fas fa-triangle-exclamation me-1"></i> Scan file not found or couldn\'t be rendered!';
    return notice;
}

/**
 * Wires the report dialogs opened from the data capture alert ([data-report] links),
 * and the "Add unrecognized page to..." form.
 */
export function initReports(config: ReportsConfig): void {
    const addDialogEl = byId('add-unrecognized-page-dialog');
    const addDialog = new LocalModal(addDialogEl);
    const addForm = byId<HTMLFormElement>('add-unrecognized-page-form');
    const addImageInput = byId<HTMLInputElement>('unrecognized-img-src');

    // -----------------------------------------------------------------------
    // Reports
    // -----------------------------------------------------------------------

    function showMissing(): void {
        new ReportModal({
            title: TITLES.missing,
            headers: ['Copy', 'Page'],
            rows: config.missingPages.flatMap((copy) =>
                copy.missing_pages.map((page) => tableRow([String(copy.copy_no), String(page)])),
            ),
            emptyMessage: 'No missing pages.',
        }).show();
    }

    function showOverwritten(): void {
        new ReportModal({
            title: TITLES.overwritten,
            headers: ['Copy', 'Page', 'Modified'],
            rows: config.overwrittenPages.map((page) => tableRow([
                String(page.student),
                String(page.page),
                page.timestamp_auto ? new Date(page.timestamp_auto * 1000).toLocaleString() : '',
            ])),
            emptyMessage: 'No overwritten pages.',
            pageLength: 50,
        }).show();
    }

    function unrecognizedRow(page: UnrecognizedPage, report: () => ReportModal): HTMLTableRowElement {
        const scanUrl = toScanUrl(page.filepath);

        const addButton = document.createElement('button');
        addButton.type = 'button';
        addButton.className = 'btn btn-primary btn-sm text-nowrap';
        addButton.textContent = 'Add this page to...';
        addButton.addEventListener('click', () => {
            report().hide();
            openAddDialog(scanUrl);
        });

        const image = new Image(500);
        image.dataset['src'] = scanUrl; // fetched once its row is shown
        image.loading = 'lazy';
        image.alt = page.filename;
        image.style.cursor = 'pointer';
        image.addEventListener('click', () => window.open(scanUrl, '_blank'));
        image.addEventListener('error', () => {
            image.replaceWith(missingScanNotice());
            addButton.disabled = true;
            addButton.title = 'The scan file is missing';
        }, { once: true });

        return tableRow([page.filename, image, addButton]);
    }

    async function showUnrecognized(): Promise<void> {
        const options = { title: TITLES.unrecognized, headers: ['File', 'Image', 'Actions'], columns: [{}, STATIC_COLUMN, STATIC_COLUMN] };

        let pages: UnrecognizedPage[];
        try {
            pages = parseJson<UnrecognizedPage[]>(await new LoadingModal(() => postText(config.unrecognizedUrl)).result) ?? [];
        } catch (error) {
            console.error(error);
            new ReportModal({ ...options, rows: [], emptyMessage: 'Could not load the unrecognized pages.' }).show();
            return;
        }

        const report: ReportModal = new ReportModal({
            ...options,
            rows: pages.map((page) => unrecognizedRow(page, () => report)),
            emptyMessage: 'No unrecognized pages.',
        });
        report.show();
    }

    const SHOW: Record<ReportKind, () => void> = {
        missing: showMissing,
        overwritten: showOverwritten,
        unrecognized: () => void showUnrecognized(),
    };

    // -----------------------------------------------------------------------
    // Add unrecognized page
    // -----------------------------------------------------------------------

    /** Opens the "Add unrecognized page to..." form; the report reopens (reloaded) once it's closed. */
    function openAddDialog(scanUrl: string): void {
        addImageInput.value = scanUrl;
        addDialogEl.addEventListener('hidden.bs.modal', () => void showUnrecognized(), { once: true });
        addDialog.show();
    }

    addForm.addEventListener('submit', (event) => {
        event.preventDefault();
        postForm(addForm.action, {}, new FormData(addForm)) // includes the CSRF token
            .then(() => addDialog.hide())
            .catch((error: unknown) => console.error('Could not add the unrecognized page', error));
    });

    document.addEventListener('click', (event) => {
        const kind = (event.target as Element).closest<HTMLElement>('[data-report]')?.dataset['report'];
        if (kind && kind in SHOW) SHOW[kind as ReportKind]();
    });
}
