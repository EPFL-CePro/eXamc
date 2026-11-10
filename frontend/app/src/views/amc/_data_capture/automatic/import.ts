import { byId } from '@examc/helpers/dom.ts';
import { postJson } from '@examc/helpers/http.ts';

import { openProcessLog, pollJob, showProcessError, streamPost } from './process.ts';
import type { JobStarted, ReviewScanCopy } from './types.ts';

interface AutomaticImportConfig {
    examPk: string;
    zipImportUrl: string;
    importAllUrl: string;
    importPagesUrl: string;
    scans: ReviewScanCopy[];
}

/**
 * Wires the automatic data capture: import from a local zip, or from the review app
 * (all pages, or pages picked in the lists).
 */
export function initAutomaticImport(config: AutomaticImportConfig): void {
    const localForm = byId<HTMLFormElement>('amcScansFromLocalFrm');
    const copiesSelect = byId<HTMLSelectElement>('scans-copies-list');
    const fromSelect = byId<HTMLSelectElement>('scans_to_import_multiselect');
    const toSelect = byId<HTMLSelectElement>('scans_to_import_multiselect_to');
    const importSelectedButton = byId<HTMLButtonElement>('importSelectedPagesBt');

    // -----------------------------------------------------------------------
    // Imports
    // -----------------------------------------------------------------------

    localForm.addEventListener('submit', (event) => {
        event.preventDefault();
        const log = openProcessLog();
        const formData = new FormData(localForm); // includes the CSRF token
        formData.append('exam_pk', config.examPk);
        streamPost(log, config.zipImportUrl, formData).catch((error: unknown) => showProcessError(log, error));
    });

    async function runReviewImport(url: string, fields: Record<string, string[]> = {}): Promise<void> {
        const log = openProcessLog();
        try {
            const job = await postJson<JobStarted>(url, fields);
            log.setOutput('AMC import job started ...\n');
            await pollJob(log, job.status_url);
        } catch (error) {
            showProcessError(log, error);
        }
    }

    byId('import-all-from-review-btn').addEventListener('click', () => void runReviewImport(config.importAllUrl));

    importSelectedButton.addEventListener('click', () => {
        const paths = Array.from(toSelect.options, (option) => option.value);
        void runReviewImport(config.importPagesUrl, { 'pages_list[]': paths }); // key read by the view
    });

    // -----------------------------------------------------------------------
    // Page picker: copy -> its pages -> selected pages (can span several copies)
    // -----------------------------------------------------------------------

    let currentCopy = 0;

    function renderCopies(): void {
        if (config.scans.length === 0) {
            const empty = new Option('No copies available', '', true, true);
            empty.disabled = true;
            copiesSelect.replaceChildren(empty);
            return;
        }
        copiesSelect.replaceChildren(...config.scans.map((copy, index) => new Option(String(copy.copy), String(index))));
        copiesSelect.value = String(currentCopy);
    }

    /** Lists the current copy's pages, leaving out the selected ones. */
    function renderPages(): void {
        const taken = new Set(Array.from(toSelect.options, (option) => option.value));
        const pages = config.scans[currentCopy]?.pages ?? [];
        fromSelect.replaceChildren(...pages.filter((p) => !taken.has(p.path)).map((p) => new Option(p.page, p.path)));
    }

    function move(direction: 'add' | 'remove', all: boolean): void {
        const source = direction === 'add' ? fromSelect : toSelect;
        const options = all ? Array.from(source.options) : Array.from(source.selectedOptions);
        const copy = config.scans[currentCopy];

        for (const option of options) {
            if (direction === 'remove') {
                option.remove();
            } else if (copy) {
                option.selected = false;
                option.text = `Copy ${copy.copy} / ${option.text}`;
                toSelect.append(option);
            }
        }
        if (direction === 'remove') renderPages(); // removed pages of the current copy come back
        importSelectedButton.disabled = toSelect.options.length === 0;
    }

    copiesSelect.addEventListener('change', () => {
        currentCopy = Number(copiesSelect.value);
        renderPages();
    });
    byId('scans_to_import_multiselect_rightAll').addEventListener('click', () => move('add', true));
    byId('scans_to_import_multiselect_rightSelected').addEventListener('click', () => move('add', false));
    byId('scans_to_import_multiselect_leftSelected').addEventListener('click', () => move('remove', false));
    byId('scans_to_import_multiselect_leftAll').addEventListener('click', () => move('remove', true));
    fromSelect.addEventListener('dblclick', () => move('add', false));
    toSelect.addEventListener('dblclick', () => move('remove', false));

    renderCopies();
    renderPages();
    importSelectedButton.disabled = true;
}
