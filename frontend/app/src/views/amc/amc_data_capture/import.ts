import { byId } from '@examc/helpers/dom.ts';
import { postJson } from '@examc/helpers/http.ts';

import { appendOutput, openProcess, pollJob, setOutput, showProcessError, streamPost } from './process.ts';
import type { JobStarted, ReviewScanCopy } from './types.ts';
import {getModal} from "@examc/helpers/modals.ts";

interface AutomaticImportConfig {
    examPk: string;
    zipImportUrl: string;
    importAllUrl: string;
    importPagesUrl: string;
    scans: ReviewScanCopy[];
}

const PROCESS_TITLE = 'Automatic data capture processing';

/**
 * Wires the "Automatic" data capture dialog: import from a local zip, or from the review app
 * (all pages, or pages picked in the two lists).
 */
export function initAutomaticImport(config: AutomaticImportConfig): void {
    const dialog = byId('confirmAutomaticDataCaptureModal');
    const localForm = byId<HTMLFormElement>('amcScansFromLocalFrm');
    const zipInput = byId<HTMLInputElement>('amc_scans_zip_file');
    const copiesSelect = byId<HTMLSelectElement>('scans-copies-list');
    const fromSelect = byId<HTMLSelectElement>('scans_to_import_multiselect');
    const toSelect = byId<HTMLSelectElement>('scans_to_import_multiselect_to');
    const importSelectedButton = byId<HTMLButtonElement>('importSelectedPagesBt');

    /** Closes the dialog and opens the process output. */
    function startProcess(): void {
        getModal({ type: "local", element: dialog }).hide();

        openProcess(PROCESS_TITLE);
    }

    // -----------------------------------------------------------------------
    // Import sources
    // -----------------------------------------------------------------------

    byId('open-automatic-capture-btn').addEventListener('click', () => {
        getModal({ type: "local", element: dialog }).show();
    });

    // Show the chosen file name in the custom file input's label
    zipInput.addEventListener('change', () => {
        const label = zipInput.parentElement?.querySelector('.custom-file-label');
        if (!label) return;
        label.textContent = zipInput.files?.[0]?.name ?? 'Select scans';
        label.classList.add('selected');
    });

    localForm.addEventListener('submit', (event) => {
        event.preventDefault();
        startProcess();

        const formData = new FormData(localForm); // includes the form's CSRF token
        formData.append('exam_pk', config.examPk);
        streamPost(config.zipImportUrl, formData)
            .then(() => appendOutput('** AUTOMATIC DATACAPTURE COMPLETED! **'))
            .catch(showProcessError);
    });

    /** Starts a review import job and follows it. */
    async function runReviewImport(url: string, fields: Record<string, string[]> = {}): Promise<void> {
        startProcess();
        try {
            const job = await postJson<JobStarted>(url, fields);
            setOutput('AMC import job started ...\n');
            await pollJob(job.status_url);
        } catch (error) {
            showProcessError(error);
        }
    }

    byId('import-all-from-review-btn').addEventListener('click', () => {
        void runReviewImport(config.importAllUrl);
    });

    importSelectedButton.addEventListener('click', () => {
        const paths = Array.from(toSelect.options, (option) => option.value);
        // 'pages_list[]' is the key jQuery used for arrays, which the view reads
        void runReviewImport(config.importPagesUrl, { 'pages_list[]': paths });
    });

    // -----------------------------------------------------------------------
    // Page picker: copies list -> pages of that copy -> selected pages
    // -----------------------------------------------------------------------

    let currentCopy = 0;

    function selectedPaths(): Set<string> {
        return new Set(Array.from(toSelect.options, (option) => option.value));
    }

    function updateImportSelectedButton(): void {
        importSelectedButton.disabled = toSelect.options.length === 0;
    }

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

    /** Lists the current copy's pages, leaving out those already selected. */
    function renderPages(): void {
        const taken = selectedPaths();
        const pages = config.scans[currentCopy]?.pages ?? [];
        fromSelect.replaceChildren(
            ...pages.filter((p) => !taken.has(p.path)).map((p) => new Option(p.page, p.path)),
        );
    }

    function addToSelection(all: boolean): void {
        const copy = config.scans[currentCopy];
        if (!copy) return;
        const options = all ? Array.from(fromSelect.options) : Array.from(fromSelect.selectedOptions);
        for (const option of options) {
            option.selected = false;
            option.text = `Copy ${copy.copy} / ${option.text}`; // selections can span several copies
            toSelect.append(option);
        }
        updateImportSelectedButton();
    }

    function removeFromSelection(all: boolean): void {
        const options = all ? Array.from(toSelect.options) : Array.from(toSelect.selectedOptions);
        for (const option of options) option.remove();
        renderPages(); // removed pages of the current copy reappear on the left
        updateImportSelectedButton();
    }

    copiesSelect.addEventListener('change', () => {
        currentCopy = Number(copiesSelect.value);
        renderPages();
    });

    byId('scans_to_import_multiselect_rightAll').addEventListener('click', () => addToSelection(true));
    byId('scans_to_import_multiselect_rightSelected').addEventListener('click', () => addToSelection(false));
    byId('scans_to_import_multiselect_leftSelected').addEventListener('click', () => removeFromSelection(false));
    byId('scans_to_import_multiselect_leftAll').addEventListener('click', () => removeFromSelection(true));
    fromSelect.addEventListener('dblclick', () => addToSelection(false));
    toSelect.addEventListener('dblclick', () => removeFromSelection(false));

    renderCopies();
    renderPages();
    updateImportSelectedButton();
}
