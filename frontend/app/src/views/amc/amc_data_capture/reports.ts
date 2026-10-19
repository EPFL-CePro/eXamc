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

type ReportKind = 'missing' | 'unrecognized' | 'overwritten';

const TITLES: Record<ReportKind, string> = {
    missing: 'Missing pages',
    unrecognized: 'Unrecognized pages',
    overwritten: 'Overwritten pages',
};

/** Columns holding an image or a button: neither sorted nor searched. */
const STATIC_COLUMN = { orderable: false, searchable: false };

function isReportKind(value: string | undefined): value is ReportKind {
    return value !== undefined && value in TITLES;
}

function formatTimestamp(seconds: number | null): string {
    return seconds ? new Date(seconds * 1000).toLocaleString() : '';
}

/**
 * Builds a table row; strings are added as text, never as HTML.
 *
 * @param {(string | Node)[]} cells - The cells' content.
 * @return {HTMLTableRowElement} The row.
 */
function tableRow(cells: (string | Node)[]): HTMLTableRowElement {
    const tr = document.createElement('tr');
    for (const cell of cells) {
        const td = document.createElement('td');
        td.append(cell);
        tr.append(td);
    }
    return tr;
}

/**
 * Shown instead of a scan whose file can't be loaded.
 *
 * @return {HTMLElement} The notice.
 */
function missingScanNotice(): HTMLElement {
    const icon = document.createElement('i');
    icon.className = 'fas fa-triangle-exclamation me-1';

    const notice = document.createElement('span');
    notice.className = 'text-danger';
    notice.append(icon, " Scan file not found or couldn't be rendered !");
    return notice;
}

/**
 * Wires the report dialogs opened from the data capture alerts ([data-report] buttons),
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
                formatTimestamp(page.timestamp_auto),
            ])),
            emptyMessage: 'No overwritten pages.',
        }).show();
    }

    async function showUnrecognized(): Promise<void> {
        const headers = ['File', 'Image', 'Actions'];
        const columns = [{}, STATIC_COLUMN, STATIC_COLUMN];

        let pages: UnrecognizedPage[];
        try {
            pages = parseJson<UnrecognizedPage[]>(await new LoadingModal(() => postText(config.unrecognizedUrl)).result) ?? [];
        } catch (error) {
            console.error(error);
            new ReportModal({
                title: TITLES.unrecognized,
                headers,
                rows: [],
                columns,
                emptyMessage: 'Could not load the unrecognized pages.',
            }).show();
            return;
        }

        const report = new ReportModal({
            title: TITLES.unrecognized,
            headers,
            rows: pages.map((page) => {
                const scanUrl = toScanUrl(page.filepath);

                const addButton = document.createElement('button');
                addButton.type = 'button';
                addButton.className = 'btn btn-primary btn-sm';
                addButton.style.width = "9rem";
                addButton.textContent = 'Add this page to...';
                addButton.addEventListener('click', () => {
                    report.hide();
                    openAddDialog(scanUrl);
                });

                const image = new Image(500);
                image.dataset['src'] = scanUrl; // fetched once its row is shown
                image.loading = 'lazy';
                image.alt = page.filename;
                image.style.cursor = 'pointer';
                image.addEventListener('click', () => window.open(scanUrl, '_blank'));

                // The scan file is gone (404) or can't be read: say so, and don't offer to add it.
                image.addEventListener('error', () => {
                    image.replaceWith(missingScanNotice());
                    addButton.disabled = true;
                    addButton.title = 'The scan file is missing';
                }, { once: true });

                return tableRow([page.filename, image, addButton]);
            }),
            columns,
            emptyMessage: 'No unrecognized pages.',
        });
        report.show();
    }

    function showReport(kind: ReportKind): void {
        if (kind === 'missing') showMissing();
        else if (kind === 'overwritten') showOverwritten();
        else void showUnrecognized();
    }

    // -----------------------------------------------------------------------
    // Add unrecognized page
    // -----------------------------------------------------------------------

    /**
     * Opens the "Add unrecognized page to..." form. Once it's closed (added or not), the unrecognized
     * pages report opens again, reloaded: an added page may now be recognized.
     *
     * @param {string} scanUrl - The scan to add.
     */
    function openAddDialog(scanUrl: string): void {
        addImageInput.value = scanUrl;
        addDialogEl.addEventListener('hidden.bs.modal', () => void showUnrecognized(), { once: true });
        addDialog.show();
    }

    addForm.addEventListener('submit', (event) => {
        event.preventDefault();
        postForm(addForm.action, {}, new FormData(addForm)) // includes the form's CSRF token
            .then(() => addDialog.hide())
            .catch((error: unknown) => console.error('Could not add the unrecognized page', error));
    });

    // -----------------------------------------------------------------------
    // Openers
    // -----------------------------------------------------------------------

    document.addEventListener('click', (event) => {
        const button = (event.target as Element).closest<HTMLElement>('[data-report]');
        const kind = button?.dataset['report'];
        if (isReportKind(kind)) showReport(kind);
    });
}