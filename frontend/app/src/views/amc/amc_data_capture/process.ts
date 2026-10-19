import { sleep } from '@examc/helpers/dom.ts';
import { getJson, HttpError } from '@examc/helpers/http.ts';
import { LogModal } from '@examc/modals';

import type { JobStatus } from './types.ts';

const POLL_INTERVAL_MS = 2000;

/**
 * Opens a new process output dialog. Each run gets its own: the dialog is removed once closed.
 *
 * @param {string} title - The dialog's title.
 * @return {LogModal} The dialog, to write the process output into.
 */
export function openProcess(title: string): LogModal {
    const log = new LogModal();
    log.setTitle(title);
    log.setOutput('');
    log.show();
    return log;
}

/**
 * Shows a failed request in the output: the HTTP status and server message, or a hint when no response came back.
 *
 * @param {LogModal} log - The process output.
 * @param {unknown} error - What the request threw.
 */
export function showProcessError(log: LogModal, error: unknown): void {
    if (error instanceof HttpError) {
        log.setOutput(`Error occurred (${error.status})\n${error.body}\n`);
        return;
    }

    log.setOutput(
        'Error occurred (request interrupted before a server response)\n'
        + 'The browser did not receive an HTTP response. Check whether the request was canceled, '
        + 'the connection timed out, or the proxy/server closed the stream.\n'
        + `${String(error)}\n`,
    );
}

/**
 * POSTs form data and streams the response text into the output as it arrives.
 *
 * @param {LogModal} log - The process output.
 * @param {string} url - The URL to post to.
 * @param {FormData} body - The form data (must include the CSRF token).
 * @throws {HttpError} If the response status is not OK.
 */
export async function streamPost(log: LogModal, url: string, body: FormData): Promise<void> {
    const response = await fetch(url, { method: 'POST', body, credentials: 'same-origin' });
    if (!response.ok) throw new HttpError(response.status, url, await response.text());

    const reader = response.body?.getReader();
    if (!reader) {
        log.appendToOutput(await response.text());
        return;
    }

    const decoder = new TextDecoder();
    for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        log.appendToOutput(decoder.decode(value, { stream: true }));
    }
    log.appendToOutput(decoder.decode());
}

/**
 * Polls a background job until it finishes, showing its output as it goes.
 *
 * @param {LogModal} log - The process output.
 * @param {string} statusUrl - The job's status URL.
 */
export async function pollJob(log: LogModal, statusUrl: string): Promise<void> {
    for (;;) {
        await sleep(POLL_INTERVAL_MS);

        let status: JobStatus;
        try {
            status = await getJson<JobStatus>(statusUrl);
        } catch (error) {
            showJobRequestError(log, error);
            return;
        }

        log.setOutput(status.output || 'Processing ...\n');
        if (status.status === 'queued' || status.status === 'running') continue;

        if (status.status === 'done') log.appendToOutput('** AUTOMATIC DATACAPTURE COMPLETED! **');
        else log.appendToOutput(`Error occurred\n${status.error || 'Unknown error'}\n`);
        return;
    }
}

/** A failed status request may still carry the job's output and error as JSON. */
function showJobRequestError(log: LogModal, error: unknown): void {
    if (error instanceof HttpError) {
        try {
            const body = JSON.parse(error.body) as Partial<JobStatus>;
            if (body.output) log.setOutput(body.output);
            if (body.error) {
                log.appendToOutput(`Error occurred\n${body.error}\n`);
                return;
            }
        } catch {
            // not JSON: fall through to the generic message
        }
    }
    showProcessError(log, error);
}