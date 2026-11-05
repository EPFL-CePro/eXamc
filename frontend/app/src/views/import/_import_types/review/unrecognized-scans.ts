import { describeFailure, failureJson, postForm } from '@examc/helpers/http.ts';
import { showToast } from '@examc/helpers/toasts.ts';

import { ScanPreviewModal } from './scan-preview-modal.ts';

const TOAST_TITLE = 'Unrecognized scans';
const SELECT_ONE = '.js-select-unrecognized-scan';
const SELECT_ALL = '.js-select-all-unrecognized-scans';

export interface UnrecognizedScans {
    unresolvedCount(): number;
    /** Reloads the table, keeping the current selection. Never rejects. */
    refresh(): Promise<void>;
}

/** Disables or enables every field and button of a form. */
function setFormDisabled(form: HTMLFormElement, disabled: boolean): void {
    for (const element of form.elements) {
        if (
            element instanceof HTMLInputElement || element instanceof HTMLSelectElement
            || element instanceof HTMLButtonElement || element instanceof HTMLTextAreaElement
        ) {
            element.disabled = disabled;
        }
    }
}

/**
 * Table of scans that couldn't be matched to a copy. Its content is reloaded from the server,
 * so it only looks inside the container, and its listeners are on the container rather than on rows.
 *
 * @param container - Holds the table; its content is replaced on each reload.
 * @param refreshUrl - Where the table's HTML is reloaded from. Without it, the table isn't reloaded.
 * @param onReloaded - Called each time the table is reloaded, e.g. after a scan is assigned.
 */
export function initUnrecognizedScans(
    container: HTMLElement,
    refreshUrl: string | undefined,
    onReloaded: () => void,
): UnrecognizedScans {
    const checkboxes = () => [...container.querySelectorAll<HTMLInputElement>(SELECT_ONE)];

    function updateSelection(): void {
        const boxes = checkboxes();
        const selected = boxes.filter(box => box.checked).length;

        container.querySelectorAll('.js-selected-scan-count').forEach(count => count.textContent = String(selected));
        container.querySelectorAll<HTMLButtonElement>('.js-delete-selected-scans-button')
            .forEach(button => button.disabled = selected === 0);
        container.querySelectorAll<HTMLInputElement>(SELECT_ALL).forEach(box => {
            box.checked = boxes.length > 0 && selected === boxes.length;
            box.indeterminate = selected > 0 && selected < boxes.length;
        });
    }

    /**
     * Sends a form of the table in the background, then reloads the table: used to assign a scan,
     * and to delete one or the selected ones. The server answers with `message`, and `errors` for the
     * scans it couldn't handle; or with `error` and an error status.
     *
     * @param form - The form to send; locked while it's sent.
     * @param fallbacks - Shown when the server gives no message: on success, and on failure.
     */
    async function send(form: HTMLFormElement, fallbacks: { done: string; failed: string }): Promise<void> {
        // Built before the fields are disabled, as disabled fields are left out.
        const body = new FormData(form);
        setFormDisabled(form, true);

        try {
            const response = await postForm(form.action, {}, body);
            const json = await response.json().catch(() => ({})) as { message?: string; errors?: string[] };
            showToast(json.message || fallbacks.done, { title: TOAST_TITLE });
            json.errors?.forEach(error => showToast(error, { error: true, title: TOAST_TITLE }));
            await refresh();
        } catch (error) {
            const failure = describeFailure(error);
            const json = failureJson<{ error: string; errors: string[] }>(failure);
            const message = json.error
                || (failure.status
                    ? `${fallbacks.failed} (error ${failure.status}).`
                    : `${fallbacks.failed}. Check your connection and try again.`);
            showToast(message, { error: true, title: TOAST_TITLE });
            json.errors?.forEach(item => showToast(item, { error: true, title: TOAST_TITLE }));
        } finally {
            // Still there when the request failed, or when the table couldn't be reloaded.
            if (form.isConnected) setFormDisabled(form, false);
        }
    }

    container.addEventListener('change', event => {
        const target = event.target;
        if (!(target instanceof HTMLInputElement)) return;

        if (target.matches(SELECT_ALL)) {
            checkboxes().forEach(box => box.checked = target.checked);
            updateSelection();
        } else if (target.matches(SELECT_ONE)) {
            updateSelection();
        }
    });

    container.addEventListener('submit', event => {
        const form = event.target;
        if (!(form instanceof HTMLFormElement)) return;

        // Every form of the table is sent in the background: the page stays where it is.
        if (form.matches('.js-assign-unrecognized-scan')) {
            event.preventDefault();
            void send(form, { done: 'The scan was assigned.', failed: 'The scan couldn\'t be assigned' });
        } else if (form.matches('.js-delete-selected-scans')) {
            event.preventDefault();
            const count = checkboxes().filter(box => box.checked).length;
            if (count && window.confirm(`Permanently delete ${count} selected scan(s)? This cannot be undone.`)) {
                void send(form, { done: 'The selected scans were deleted.', failed: 'The scans couldn\'t be deleted' });
            }
        } else if (form.matches('.js-delete-unrecognized-scan')) {
            event.preventDefault();
            const filename = form.dataset['filename'] ?? '';
            if (window.confirm(`Permanently delete scan "${filename}"? This cannot be undone.`)) {
                void send(form, { done: 'The scan was deleted.', failed: 'The scan couldn\'t be deleted' });
            }
        }
    });

    container.addEventListener('click', event => {
        const button = (event.target as Element).closest<HTMLElement>('.js-unrecognized-scan-preview');
        if (!button) return;

        event.preventDefault();
        new ScanPreviewModal({
            imageUrl: button.dataset['imgUrl'] ?? '',
            title: button.dataset['title'] ?? '',
        }).show();
    });

    /** The reload in progress, if any: asking again meanwhile waits for it rather than starting another. */
    let reloading: Promise<void> | null = null;

    function refresh(): Promise<void> {
        reloading ??= reload().finally(() => reloading = null);
        return reloading;
    }

    async function reload(): Promise<void> {
        if (!refreshUrl) return;
        try {
            const response = await fetch(refreshUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const html = await response.text();

            const selectedIds = new Set(checkboxes().filter(box => box.checked).map(box => box.value));
            container.innerHTML = html;
            checkboxes().forEach(box => box.checked = selectedIds.has(box.value));

            updateSelection();
            onReloaded();
        } catch (error) {
            console.error('Could not refresh the unrecognized scans table', error);
            showToast('The list of unrecognized scans couldn\'t be refreshed. Reload the page to see it.', { error: true });
        }
    }

    updateSelection();

    return {
        unresolvedCount: () => container.querySelectorAll('.js-unrecognized-scan-row').length,
        refresh,
    };
}