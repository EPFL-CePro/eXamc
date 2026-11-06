import { sleep } from '@examc/helpers/dom.ts';
import { getJson, HttpError } from '@examc/helpers/http.ts';
import { LogModal } from '@examc/modals';

import type { JobStatus } from './types.ts';

const POLL_INTERVAL_MS = 2000;
const COMPLETED = '** AUTOMATIC DATACAPTURE COMPLETED! **';

/** Opens a new output dialog for one import run (removed once closed). */
export function openProcessLog(): LogModal {
    const log = new LogModal();
    log.setTitle('Automatic data capture processing');
    log.setOutput('');
    log.show();
    return log;
}

/** Shows a failed request: the HTTP status and server message, or a hint when no response came back. */
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
 * @throws {HttpError} If the response status is not OK.
 */
export async function streamPost(log: LogModal, url: string, body: FormData): Promise<void> {
    const response = await fetch(url, { method: 'POST', body, credentials: 'same-origin' });
    if (!response.ok) throw new HttpError(response.status, url, await response.text());

    const reader = response.body?.getReader();
    if (!reader) {
        log.appendToOutput(await response.text());
    } else {
        const decoder = new TextDecoder();
        for (let chunk = await reader.read(); !chunk.done; chunk = await reader.read()) {
            log.appendToOutput(decoder.decode(chunk.value, { stream: true }));
        }
        log.appendToOutput(decoder.decode());
    }
    log.appendToOutput(COMPLETED);
}

/** Polls a background job until it finishes, showing its output as it goes. */
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

        log.appendToOutput(status.status === 'done' ? COMPLETED : `Error occurred\n${status.error || 'Unknown error'}\n`);
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
            // not JSON: generic message below
        }
    }
    showProcessError(log, error);
}
