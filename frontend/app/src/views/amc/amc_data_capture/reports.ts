import { byId } from '@examc/helpers/dom.ts';
import { parseJson, postForm, postText, toScanUrl } from '@examc/helpers/http.ts';

import type { MissingPagesCopy, OverwrittenPage, UnrecognizedPage } from './types.ts';
import {getModal} from "@examc/helpers/modals.ts";

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

function isReportKind(value: string | undefined): value is ReportKind {
    return value !== undefined && value in TITLES;
}

function formatTimestamp(seconds: number | null): string {
    return seconds ? new Date(seconds * 1000).toLocaleString() : '';
}

/**
 * Wires the report dialogs opened from the data capture alerts ([data-report] buttons),
 * and the "Add unrecognized page to..." form.
 */
export function initReports(config: ReportsConfig): void {
    const dialog = byId('errorDataCaptureDialog');
    const dialogTitle = byId('errorDataCaptureDialogTitle');
    const head = byId<HTMLTableSectionElement>('errorDataCaptureDialogTHead');
    const body = byId<HTMLTableSectionElement>('errorDataCaptureDialogTBody');

    const addDialog = byId('addUnrecognizedPageDialog');
    const addForm = byId<HTMLFormElement>('addUnrecognizedPageFrm');
    const addImageInput = byId<HTMLInputElement>('unrecognized_img_src');

    /** Row of the unrecognized page being added, removed once the server accepted it. */
    let pendingRow: HTMLTableRowElement | null = null;
    /** Incremented on every unrecognized-pages load, so a stale response is ignored. */
    let loadToken = 0;

    // -----------------------------------------------------------------------
    // Table rendering
    // -----------------------------------------------------------------------

    /**
     * Replaces the dialog's table.
     *
     * @return {HTMLTableRowElement[]} The body rows, in order.
     */
    function fillTable(headers: string[], rows: (string | Node)[][]): HTMLTableRowElement[] {
        const headRow = document.createElement('tr');
        for (const text of headers) {
            const th = document.createElement('th');
            th.textContent = text;
            headRow.append(th);
        }
        head.replaceChildren(headRow);

        const bodyRows = rows.map((cells) => {
            const tr = document.createElement('tr');
            for (const cell of cells) {
                const td = document.createElement('td');
                td.append(cell);
                tr.append(td);
            }
            return tr;
        });
        body.replaceChildren(...bodyRows);
        return bodyRows;
    }

    function showMissing(): void {
        fillTable(['Copy', 'Page'], config.missingPages.flatMap((copy) =>
            copy.missing_pages.map((page) => [String(copy.copy_no), String(page)]),
        ));
    }

    function showOverwritten(): void {
        fillTable(['Copy', 'Page', 'Modified'], config.overwrittenPages.map((page) => [
            String(page.student),
            String(page.page),
            formatTimestamp(page.timestamp_auto),
        ]));
    }

    async function showUnrecognized(): Promise<void> {
        const token = ++loadToken;
        fillTable(['File', 'Image', ''], [['Loading…']]);

        let pages: UnrecognizedPage[];
        try {
            pages = parseJson<UnrecognizedPage[]>(await postText(config.unrecognizedUrl)) ?? [];
        } catch (error) {
            if (token === loadToken) fillTable(['File', 'Image', ''], [['Could not load the unrecognized pages.']]);
            console.error(error);
            return;
        }
        if (token !== loadToken) return;

        const addButtons: HTMLButtonElement[] = [];
        const rows = fillTable(['File', 'Image', ''], pages.map((page) => {
            const scanUrl = toScanUrl(page.filepath);

            const image = new Image(500);
            image.src = scanUrl;
            image.alt = page.filename;
            image.style.cursor = 'pointer';
            image.addEventListener('click', () => window.open(scanUrl, '_blank'));

            const addButton = document.createElement('button');
            addButton.type = 'button';
            addButton.className = 'btn btn-primary btn-sm';
            addButton.textContent = 'Add this page to...';
            addButton.dataset['scanUrl'] = scanUrl;
            addButtons.push(addButton);

            return [page.filename, image, addButton];
        }));

        // Rows only exist once the table is filled, so the buttons are wired afterwards.
        addButtons.forEach((button, i) => {
            const row = rows[i];
            if (row) button.addEventListener('click', () => openAddDialog(button.dataset['scanUrl'] ?? '', row));
        });
    }

    function showReport(kind: ReportKind): void {
        dialogTitle.textContent = TITLES[kind];
        if (kind === 'missing') showMissing();
        else if (kind === 'overwritten') showOverwritten();
        else void showUnrecognized();
        const modal = getModal({ type: "local", element: dialog });
        modal.show();
    }

    // -----------------------------------------------------------------------
    // Add unrecognized page
    // -----------------------------------------------------------------------

    function openAddDialog(scanUrl: string, row: HTMLTableRowElement): void {
        addImageInput.value = scanUrl;
        pendingRow = row;
        const modal = getModal({ type: "local", element: dialog });
        modal.show();
    }

    addForm.addEventListener('submit', (event) => {
        event.preventDefault();
        postForm(addForm.action, {}, new FormData(addForm)) // includes the form's CSRF token
            .then(() => {
                pendingRow?.remove();
                pendingRow = null;

                const modal = getModal({ type: "local", element: dialog });
                modal.hide();

                void showUnrecognized(); // refresh: the page may now be recognized
            })
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
