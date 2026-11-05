import { describeFailure, failureJson, postForm } from '@examc/helpers/http.ts';
import { showToast } from '@examc/helpers/toasts.ts';

import type { HttpProgressBar } from '@examc/helpers/http.ts';

const TOAST_TITLE = 'Scans upload';
const POLL_INTERVAL_MS = 2000;
const AJAX_HEADERS = { 'X-Requested-With': 'XMLHttpRequest' };

const megabytes = new Intl.NumberFormat(undefined, { style: 'unit', unit: 'megabyte', maximumFractionDigits: 1 });

/** What upload_scans answers once the import task has started (202). */
interface UploadAccepted {
    message: string;
    task_id: string;
    status_url: string;
    cancel_url: string;
}

/** What upload_scans_status answers. */
interface UploadStatus {
    status: 'running' | 'done' | 'failed';
    progress?: { current: number; total: number; description?: string };
    /** Set while the task runs. */
    cancel_url?: string;
    /** How many scans of the exam are unrecognized right now. */
    unrecognized_count?: number;
    error?: string;
    cancelled?: boolean;
}

/** The server answered, but with an error. Its message is meant for the user. */
class UploadError extends Error {}

/** The upload was aborted, or the import cancelled, from this page or another. */
class CancelledError extends Error {}

function parseJson(text: string): Record<string, unknown> | null {
    try {
        const value: unknown = JSON.parse(text);
        return value && typeof value === 'object' ? value as Record<string, unknown> : null;
    } catch {
        return null;
    }
}

/**
 * Posts the form with XMLHttpRequest rather than fetch, which can't report upload progress.
 * Resolves with the response once the server has answered, whatever its status.
 */
function postWithProgress(
    url: string,
    body: FormData,
    signal: AbortSignal,
    onProgress: (loaded: number, total: number) => void,
): Promise<{ status: number; text: string }> {
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('POST', url);
        xhr.setRequestHeader('X-Requested-With', AJAX_HEADERS['X-Requested-With']);
        xhr.upload.addEventListener('progress', event => {
            if (event.lengthComputable) onProgress(event.loaded, event.total);
        });
        xhr.addEventListener('load', () => resolve({ status: xhr.status, text: xhr.responseText }));
        xhr.addEventListener('error', () => reject(new Error('Network error')));
        xhr.addEventListener('abort', () => reject(new CancelledError('Upload aborted')));
        signal.addEventListener('abort', () => xhr.abort(), { once: true });
        xhr.send(body);
    });
}

const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

/**
 * Waits until the scans import task is done, reporting its progress. Throws if it failed or was cancelled.
 * Stops quietly, without throwing, once `signal` is aborted.
 */
/** What each status check passes on. */
interface StatusCallbacks {
    onCancelUrl: (url: string) => void;
    onUnrecognizedCount?: (count: number) => void;
}

async function waitForImport(
    statusUrl: string,
    progress: HttpProgressBar,
    { onCancelUrl, onUnrecognizedCount }: StatusCallbacks,
    signal?: AbortSignal,
): Promise<void> {
    for (;;) {
        if (signal?.aborted) return;
        const response = await fetch(statusUrl, { headers: AJAX_HEADERS, credentials: 'same-origin', signal: signal ?? null });
        
        if (!response.ok) {
            const error = parseJson(await response.text())?.['error'];
            throw new UploadError(typeof error === 'string' ? error : `The import status couldn't be read (error ${response.status}).`);
        }

        const task = await response.json() as UploadStatus;
        if (signal?.aborted) return;
        if (task.cancel_url) onCancelUrl(task.cancel_url);
        if (task.unrecognized_count !== undefined) onUnrecognizedCount?.(task.unrecognized_count);
        if (task.status === 'done') return;
        if (task.status === 'failed') {
            if (task.cancelled) throw new CancelledError(task.error || 'The scans import was cancelled.');
            throw new UploadError(task.error || 'The scans couldn\'t be imported.');
        }

        if (task.progress) {
            const { current, total, description } = task.progress;
            const percent = Math.min(100, (current / total) * 100);
            progress.show(description || 'Importing the scans…', percent, `${Math.round(percent)}%`);
        } else {
            progress.show('Importing the scans…');
        }

        await sleep(POLL_INTERVAL_MS);
    }
}

export interface UploadHooks {
    /** The server accepted the zip and started importing it. */
    onImportStarted: () => void;
    /** The import task finished. */
    onImported: () => void;
    /** The upload or the import failed, or was cancelled. */
    onFailed: () => void;
    /** Each status check, with how many scans are unrecognized right now. */
    onUnrecognizedCount?: (count: number) => void;
}

export interface UploadForm {
    /** Follows an import that's already running, e.g. one started before the page was reloaded. */
    follow(statusUrl: string): Promise<void>;
    /** Locks the form for an import that's running but can't be followed (no status URL): until a reload. */
    block(): void;
}

export interface UploadFormElements {
    form: HTMLFormElement;
    /** Shows a spinner while the upload and the import run. */
    submitButton: HTMLButtonElement;
    progress: HttpProgressBar;
    /** Stops the upload, or the import once it has started. Shown with the progress bar. */
    cancelButton: HTMLButtonElement;
    /** upload_scans_status's URL, with TASK_ID_PLACEHOLDER where the task id goes. */
    statusUrlTemplate: string;
}

/** The task id in `statusUrlTemplate`, replaced by the id the page picks for each upload. */
export const TASK_ID_PLACEHOLDER = '00000000-0000-0000-0000-000000000000';

/**
 * Sends the scans upload form in the background, so the page stays where it is, and follows the import
 * until it's done. Progress shows under the form, with a button to cancel; the result shows as a toast.
 */
export function initUploadForm(
    { form, submitButton, progress, cancelButton, statusUrlTemplate }: UploadFormElements,
    hooks: UploadHooks,
): UploadForm {
    const buttonContent = submitButton.innerHTML;
    const cancelContent = cancelButton.innerHTML;

    /** Aborts the upload while the file is being sent; null once the server has it. */
    let uploadController: AbortController | null = null;
    /** Where the running import is cancelled, given by the server once the task is known. */
    let cancelUrl: string | null = null;

    // The form stays locked until the import is over: a second upload would replace the file being imported.
    function setBusy(busyLabel: string | null): void {
        const busy = busyLabel !== null;
        form.setAttribute('aria-busy', String(busy));
        for (const element of form.elements) {
            if (element === cancelButton) continue;
            if (element instanceof HTMLInputElement || element instanceof HTMLButtonElement) element.disabled = busy;
        }
        submitButton.innerHTML = busy
            ? `<span class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span> ${busyLabel}`
            : buttonContent;
        cancelButton.disabled = !busy;
        cancelButton.innerHTML = cancelContent;
    }

    async function cancel(): Promise<void> {
        if (uploadController) {
            uploadController.abort();
            return;
        }
        if (!cancelUrl) return;

        cancelButton.disabled = true;
        cancelButton.textContent = 'Cancelling…';
        try {
            // The import then reports itself as cancelled, which ends the wait below.
            await postForm(cancelUrl);
        } catch (error) {
            const failure = describeFailure(error);
            showToast(failureJson<{ error: string }>(failure).error || 'The import couldn\'t be cancelled.',
                { error: true, title: TOAST_TITLE });
            cancelButton.disabled = false;
            cancelButton.innerHTML = cancelContent;
        }
    }

    cancelButton.addEventListener('click', () => void cancel());

    const statusCallbacks: StatusCallbacks = {
        onCancelUrl: url => cancelUrl = url,
        onUnrecognizedCount: count => hooks.onUnrecognizedCount?.(count),
    };

    async function followImport(statusUrl: string): Promise<void> {
        progress.show('Importing the scans…');
        await waitForImport(statusUrl, progress, statusCallbacks);
        showToast('The scans were imported.', { title: TOAST_TITLE });
        hooks.onImported();
    }

    /** Runs a step with the form locked; any failure or cancellation is shown as a toast. */
    async function locked(busyLabel: string, step: () => Promise<void>): Promise<void> {
        setBusy(busyLabel);
        try {
            await step();
        } catch (error) {
            if (error instanceof CancelledError) {
                showToast(error.message === 'Upload aborted' ? 'The upload was cancelled.' : error.message,
                    { title: TOAST_TITLE });
            } else {
                const message = error instanceof UploadError
                    ? error.message
                    : 'The scans could not be uploaded. Check your connection and try again.';
                showToast(message, { error: true, title: TOAST_TITLE });
            }
            hooks.onFailed();
        } finally {
            uploadController = null;
            cancelUrl = null;
            progress.hide();
            setBusy(null);
        }
    }

    form.addEventListener('submit', event => {
        event.preventDefault();

        // Built before the inputs are disabled, as disabled inputs are left out.
        const body = new FormData(form);

        // Picked here, so the import's progress can be followed before the server answers:
        // in eager mode (dev), the server only answers once the import is over.
        const taskId = crypto.randomUUID();
        body.set('task_id', taskId);
        // Without a usable template, the import is only followed once the server answers.
        const canFollowEarly = statusUrlTemplate.includes(TASK_ID_PLACEHOLDER);
        if (!canFollowEarly) console.warn('No upload status URL template: the import is followed once the upload answers.');
        const statusUrl = statusUrlTemplate.replace(TASK_ID_PLACEHOLDER, taskId);

        void locked('Uploading…', async () => {
            uploadController = new AbortController();
            const polling = new AbortController();
            let followed: Promise<void> | null = null;
            const startFollowing = () => {
                if (followed || !canFollowEarly) return;
                followed = waitForImport(statusUrl, progress, statusCallbacks, polling.signal);
                // Its failure is handled where it's awaited, once the server has answered.
                followed.catch(() => undefined);
            };

            progress.show('Uploading the zip file…', 0);
            let response: { status: number; text: string };
            try {
                response = await postWithProgress(
                    form.action,
                    body,
                    uploadController.signal,
                    (loaded, total) => {
                        // Everything is sent: from now on, the import's own progress is shown.
                        if (loaded >= total) {
                            startFollowing();
                            return;
                        }
                        progress.show(
                            'Uploading the zip file…',
                            (loaded / total) * 100,
                            `${megabytes.format(loaded / 1e6)} of ${megabytes.format(total / 1e6)}`,
                        );
                    },
                );
            } catch (error) {
                polling.abort();
                throw error;
            }
            uploadController = null;

            const json = parseJson(response.text);
            if (response.status < 200 || response.status >= 300) {
                // No task was started: there's nothing to follow.
                polling.abort();
                const error = typeof json?.['error'] === 'string' ? json['error'] : '';
                throw new UploadError(error || `The scans could not be uploaded (error ${response.status}).`);
            }

            const accepted = json as unknown as UploadAccepted;
            cancelUrl = accepted.cancel_url;
            showToast(accepted.message, { title: TOAST_TITLE });
            form.reset();
            hooks.onImportStarted();

            // The server picks another id when ours couldn't be used: that task is followed instead.
            if (accepted.status_url !== statusUrl) {
                polling.abort();
                followed = null;
            }
            if (followed) {
                await followed;
                showToast('The scans were imported.', { title: TOAST_TITLE });
                hooks.onImported();
            } else {
                await followImport(accepted.status_url);
            }
        });
    });

    return {
        follow: statusUrl => locked('Importing…', () => followImport(statusUrl)),
        block: () => {
            setBusy('Importing…');
            cancelButton.disabled = true; // nothing to cancel without the task's URL
            progress.show('Scans are being imported for this exam. Reload the page once it\'s done.');
        },
    };
}