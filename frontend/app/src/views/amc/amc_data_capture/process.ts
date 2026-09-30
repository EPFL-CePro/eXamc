import { byId } from '@examc/helpers/dom.ts';
import { getJson, HttpError } from '@examc/helpers/http.ts';

import type { JobStatus } from './types.ts';
import {getModal} from "@examc/helpers/modals.ts";

const POLL_INTERVAL_MS = 2000;

// The process modal is shared with the other AMC tabs, so its elements are looked up when used.
const processModalEl = (): HTMLElement => byId('amc_process_modal');
const titleEl = (): HTMLElement => byId('amc_process_modal_title');
const outputEl = (): HTMLElement => byId('amc_process_modal_body');

// ---------------------------------------------------------------------------
// Output
// ---------------------------------------------------------------------------

/** Opens the process modal with a title and empty output. */
export function openProcess(titleText: string): void {
    titleEl().textContent = titleText;
    setOutput('');

    const modal = getModal({ type: "local", element: processModalEl() });
    modal.show();
}

/** Replaces the whole output, keeping it scrolled to the bottom. */
export function setOutput(text: string): void {
    const body = outputEl();
    body.textContent = text;
    body.scrollTop = body.scrollHeight;
}

/** Appends text to the output, keeping it scrolled to the bottom. */
export function appendOutput(text: string): void {
    if (!text) return;
    const body = outputEl();
    body.append(text);
    body.scrollTop = body.scrollHeight;
}

/**
 * Shows a failed request in the output: the HTTP status and server message, or a hint when no response came back.
 *
 * @param {unknown} error - What the request threw.
 */
export function showProcessError(error: unknown): void {
    if (error instanceof HttpError) {
        setOutput(`Error occurred (${error.status})\n${error.body}\n`);
        return;
    }
    setOutput(
        'Error occurred (request interrupted before a server response)\n'
        + 'The browser did not receive an HTTP response. Check whether the request was canceled, '
        + 'the connection timed out, or the proxy/server closed the stream.\n'
        + `${String(error)}\n`,
    );
}

// ---------------------------------------------------------------------------
// Running processes
// ---------------------------------------------------------------------------

/**
 * POSTs form data and streams the response text into the output as it arrives.
 *
 * @param {string} url - The URL to post to.
 * @param {FormData} body - The form data (must include the CSRF token).
 * @throws {HttpError} If the response status is not OK.
 */
export async function streamPost(url: string, body: FormData): Promise<void> {
    const response = await fetch(url, { method: 'POST', body, credentials: 'same-origin' });
    if (!response.ok) throw new HttpError(response.status, url, await response.text());

    const reader = response.body?.getReader();
    if (!reader) {
        appendOutput(await response.text());
        return;
    }

    const decoder = new TextDecoder();
    for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        appendOutput(decoder.decode(value, { stream: true }));
    }
    appendOutput(decoder.decode());
}

const sleep = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Polls a background job until it finishes, showing its output as it goes.
 *
 * @param {string} statusUrl - The job's status URL.
 */
export async function pollJob(statusUrl: string): Promise<void> {
    for (;;) {
        await sleep(POLL_INTERVAL_MS);

        let status: JobStatus;
        try {
            status = await getJson<JobStatus>(statusUrl);
        } catch (error) {
            showJobRequestError(error);
            return;
        }

        setOutput(status.output || 'Processing ...\n');
        if (status.status === 'queued' || status.status === 'running') continue;

        if (status.status === 'done') appendOutput('** AUTOMATIC DATACAPTURE COMPLETED! **');
        else appendOutput(`Error occurred\n${status.error || 'Unknown error'}\n`);
        return;
    }
}

/** A failed status request may still carry the job's output and error as JSON. */
function showJobRequestError(error: unknown): void {
    if (error instanceof HttpError) {
        try {
            const body = JSON.parse(error.body) as Partial<JobStatus>;
            if (body.output) setOutput(body.output);
            if (body.error) {
                appendOutput(`Error occurred\n${body.error}\n`);
                return;
            }
        } catch {
            // not JSON: fall through to the generic message
        }
    }
    showProcessError(error);
}
