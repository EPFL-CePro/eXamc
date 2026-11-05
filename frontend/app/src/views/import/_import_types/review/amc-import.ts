import { showToast } from '@examc/helpers/toasts.ts';

import type { LogModal } from '@examc/modals/log';

const POLL_INTERVAL_MS = 2000;
const TOAST_TITLE = 'AMC import';
const AJAX_HEADERS = { 'X-Requested-With': 'XMLHttpRequest' };

interface StartResponse {
    existing?: boolean;
    status_url: string;
}

interface JobStatus {
    status: 'queued' | 'running' | 'done' | string;
    output?: string;
    error?: string;
}

class HttpError extends Error {
    constructor(readonly status: number, readonly body: string) {
        super(`HTTP ${status}`);
    }
}

/** The job itself reported a failure (as opposed to the request failing). */
class JobError extends Error {}

/** Writes to the log modal, and keeps what was written: marking's output goes under data capture's. */
class ProcessLog {
    private content = '';

    public constructor(private readonly modal: LogModal) {}

    public get text(): string {
        return this.content;
    }

    public setOutput(text = ''): void {
        this.content = text;
        this.modal.setOutput(text);
    }

    public appendOutput(text: string): void {
        this.content += text;
        this.modal.appendToOutput(text);
    }
}

function parseJson(text: string): Record<string, unknown> | null {
    try {
        const value: unknown = JSON.parse(text);
        return value && typeof value === 'object' ? value as Record<string, unknown> : null;
    } catch {
        return null;
    }
}

function showError(modal: ProcessLog, error: unknown): void {
    if (error instanceof JobError) {
        modal.appendOutput(`Error occurred\n${error.message}\n`);
        return;
    }
    if (error instanceof HttpError) {
        const json = parseJson(error.body);
        modal.setOutput(typeof json?.['output'] === 'string' ? json['output'] : '');
        modal.appendOutput(`Error occurred (${error.status})\n`);
        if (typeof json?.['error'] === 'string') modal.appendOutput(`${json['error']}\n`);
        else if (error.body) modal.appendOutput(`${error.body}\n`);
        return;
    }
    modal.setOutput();
    modal.appendOutput(`Error occurred\nError: ${error instanceof Error ? error.message : String(error)}\n`);
}

async function post(url: string, csrfToken: string, data: Record<string, string> = {}): Promise<Response> {
    const response = await fetch(url, {
        method: 'POST',
        headers: AJAX_HEADERS,
        credentials: 'same-origin',
        body: new URLSearchParams({ csrfmiddlewaretoken: csrfToken, ...data }),
    });
    if (!response.ok) throw new HttpError(response.status, await response.text());
    return response;
}

const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

async function waitForJob(modal: ProcessLog, statusUrl: string): Promise<void> {
    for (;;) {
        const response = await fetch(statusUrl, { headers: AJAX_HEADERS, credentials: 'same-origin' });
        if (!response.ok) throw new HttpError(response.status, await response.text());

        const job = await response.json() as JobStatus;
        modal.setOutput(job.output || 'Processing ...\n');

        if (job.status === 'done') return;
        if (job.status !== 'running' && job.status !== 'queued') throw new JobError(job.error || 'Unknown error');

        await sleep(POLL_INTERVAL_MS);
    }
}

/** Runs AMC marking, streaming its output under the data capture output. */
async function runMarking(modal: ProcessLog, url: string, csrfToken: string): Promise<void> {
    const prefix = `${modal.text}\n\n** START MARKING ... **\n`;
    modal.setOutput(prefix);

    const response = await post(url, csrfToken, { update_scoring_strategy: 'true' });

    if (response.body) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let output = '';
        for (;;) {
            const { done, value } = await reader.read();
            if (done) break;
            output += decoder.decode(value, { stream: true });
            modal.setOutput(prefix + output);
        }
        modal.setOutput(prefix + output + decoder.decode());
    } else {
        modal.setOutput(prefix + await response.text());
    }

    modal.appendOutput('\n** MARKING COMPLETED! **');
}

export interface AutomaticImportOptions {
    importScansUrl: string;
    callAmcMarkUrl: string;
    csrfToken: string;
    /** Called when the server answers 409 because an import is already pending. */
    onConflict: () => void;
}

/**
 * Starts AMC's automatic data capture, waits for it, then runs marking.
 * Progress and errors are shown in the given log modal.
 */
export async function runAutomaticImport(logModal: LogModal, options: AutomaticImportOptions): Promise<void> {
    const { importScansUrl, callAmcMarkUrl, csrfToken, onConflict } = options;
    const modal = new ProcessLog(logModal);
    logModal.show();

    try {
        const job = await (await post(importScansUrl, csrfToken)).json() as StartResponse;
        modal.setOutput(job.existing ? 'AMC import job already running ...\n' : 'AMC import job started ...\n');
        await waitForJob(modal, job.status_url);
    } catch (error) {
        showError(modal, error);
        if (error instanceof HttpError && error.status === 409) {
            onConflict();
            showToast('Another AMC import is already pending. This one will start after the next upload.',
                { error: true, title: TOAST_TITLE });
        } else {
            showToast('Data capture failed. The AMC process window shows the details.', { error: true, title: TOAST_TITLE });
        }
        return;
    }

    modal.appendOutput('** AUTOMATIC DATACAPTURE COMPLETED! **');

    try {
        await runMarking(modal, callAmcMarkUrl, csrfToken);
    } catch (error) {
        showError(modal, error);
        showToast('Marking failed. The AMC process window shows the details.', { error: true, title: TOAST_TITLE });
        return;
    }

    // Also shown as a toast, in case the process window was closed while it ran.
    showToast('Data capture and marking are complete.', { title: TOAST_TITLE });
}