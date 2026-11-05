import { byId, requireData } from '@examc/helpers/dom.ts';
import { HttpProgressBar } from '@examc/helpers/http.ts';
import { showToast } from '@examc/helpers/toasts.ts';
import { LogModal } from '@examc/modals/log.ts';

import { runAutomaticImport } from './amc-import.ts';
import { initUnrecognizedScans } from './unrecognized-scans.ts';
import { initUploadForm } from './upload-form.ts';

/** Django messages and the view's own message, rendered hidden in the template, shown as toasts. */
function showPageMessages(): void {
    document.querySelectorAll<HTMLElement>('#pageMessages [data-tags]').forEach(item => {
        const message = item.textContent?.trim();
        if (!message) return;

        const tags = item.dataset['tags'] ?? '';
        if (tags.includes('error')) showToast(message, { error: true });
        else if (tags.includes('warning')) showToast(message, { error: true, title: 'Warning' });
        else if (tags.includes('success')) showToast(message);
        else showToast(message, { title: 'Info' });
    });
}

document.addEventListener('DOMContentLoaded', () => {
    showPageMessages();

    const root = byId('uploadScansDiv');
    const csrfToken = requireData(root, 'csrfToken');
    const importScansUrl = requireData(root, 'importScansUrl');
    const callAmcMarkUrl = requireData(root, 'callAmcMarkUrl');

    // The running scans import is set on the whole import page: every tab is locked while it runs.
    const importPage = byId('import-page');
    // Only set while a scans import is running, e.g. one started before the page was reloaded.
    const uploadStatusUrl = importPage.dataset['uploadStatusUrl'];
    const importRunningNotice = byId('importRunningNotice');
    const importLocks = [...document.querySelectorAll<HTMLFieldSetElement>('fieldset[data-import-lock]')];

    /** Shows the notice on every tab and disables their imports, or the other way round. */
    function setImportRunning(running: boolean): void {
        importPage.dataset['uploadTaskActive'] = String(running);
        importRunningNotice.hidden = !running;
        importLocks.forEach(fieldset => fieldset.disabled = running);
    }

    // ?start_amc_import=1 forces the automatic AMC import, even if the server didn't flag it as pending.
    const forceAutoImport = new URLSearchParams(window.location.search).get('start_amc_import') === '1';

    const state = {
        pending: requireData(root, 'pendingAmcImport') === 'true' || forceAutoImport,
        uploadActive: requireData(importPage, 'uploadTaskActive') === 'true',
        started: false,
    };

    const notice = byId('pendingAmcImportNotice');
    // Each reload of the table (after an upload, or once a scan is assigned) may leave none to handle:
    // AMC import then starts, as it did when the page reloaded after each assignment.
    const tableContainer = byId('unrecognizedReviewScansTable');
    const scans = initUnrecognizedScans(tableContainer, tableContainer.dataset['refreshUrl'], () => maybeStartImport());

    function showNotice(text: string): void {
        notice.textContent = text;
        notice.hidden = false;
    }

    function updateNotice(): void {
        if (!state.pending) {
            notice.hidden = true;
            return;
        }
        if (state.uploadActive) {
            showNotice('Upload is still running. AMC import will start after upload and all unrecognized scans are assigned or deleted.');
            return;
        }
        const unresolved = scans.unresolvedCount();
        if (unresolved > 0) {
            showNotice(`Assign or delete ${unresolved} unrecognized scan(s) before AMC import starts.`);
            return;
        }
        showNotice('All unrecognized scans are assigned or deleted. AMC import is starting.');
    }

    function maybeStartImport(): void {
        updateNotice();
        if (!state.pending || state.uploadActive || state.started || scans.unresolvedCount() > 0) return;

        state.started = true;
        state.pending = false;
        updateNotice();

        // A new modal for each run: it's removed from the page once closed.
        const logModal = new LogModal();
        logModal.setTitle('Automatic data capture processing');
        void runAutomaticImport(logModal, {
            importScansUrl,
            callAmcMarkUrl,
            csrfToken,
            // 409: another import is already queued, so retry once the next upload completes.
            onConflict: () => {
                state.pending = true;
                state.started = false;
                updateNotice();
            },
        });
    }

    /** The scans are imported: new unrecognized ones may be listed, then AMC import can start. */
    function onUploadFinished(): void {
        state.uploadActive = false;
        void scans.refresh().then(maybeStartImport);
    }

    maybeStartImport();

    if (forceAutoImport) window.history.replaceState({}, document.title, window.location.pathname);

    const moreScansButton = byId<HTMLButtonElement>('moreUnrecognizedScansButton');
    moreScansButton.addEventListener('click', () => window.location.reload());

    // Only rendered once an AMC project has been imported.
    const uploadForm = document.getElementById('uploadScansForm');
    const uploadButton = uploadForm?.querySelector('button[type="submit"]');
    if (uploadForm instanceof HTMLFormElement && uploadButton instanceof HTMLButtonElement) {
        const upload = initUploadForm({
            form: uploadForm,
            submitButton: uploadButton,
            progress: new HttpProgressBar(byId('uploadScansProgress')),
            cancelButton: byId<HTMLButtonElement>('uploadScansCancel'),
            statusUrlTemplate: importPage.dataset['uploadStatusUrlTemplate'] ?? '',
        }, {
            // New scans: AMC import runs again once they're imported and every unrecognized one is handled.
            onImportStarted: () => {
                state.pending = true;
                state.started = false;
                state.uploadActive = true;
                setImportRunning(true);
                updateNotice();
            },
            onImported: () => {
                setImportRunning(false);
                onUploadFinished();
            },
            onFailed: () => {
                state.pending = false;
                state.uploadActive = false;
                setImportRunning(false);
                updateNotice();
            },
            // While the import runs: scans not in the table yet are announced; the page is reloaded on click.
            onUnrecognizedCount: count => {
                if (count > scans.unresolvedCount()) moreScansButton.hidden = false;
            },
        });

        // An import running from before the page loaded: followed like a new one, or at least
        // blocks the form when the page wasn't given its status URL.
        if (state.uploadActive) {
            if (uploadStatusUrl) void upload.follow(uploadStatusUrl);
            else upload.block();
        }
    }
});