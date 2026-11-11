import { sleep } from '@examc/helpers/dom.ts';
import { getJson, parseJson, postForm } from '@examc/helpers/http.ts';

import { ModuleUninitialized } from './errors.ts';
import type { AnnotateStartResponse, AnnotateStatusResponse, AnnotateUrls } from './types.ts';

const POLL_INTERVAL_MS = 2000;
const MAX_POLL_FAILURES = 5;

let urls: AnnotateUrls | null = null;

/** Sets the API endpoints. Called by index.ts once the DOM has loaded. */
export function initAnnotate(endpoints: AnnotateUrls): void {
    urls = endpoints;
}

/** Thrown when the job's status can't be fetched anymore: the job may still finish on the server. */
export class LostContactError extends Error {
    constructor() {
        super('Lost contact with the server while annotating');
        this.name = 'LostContactError';
        Object.setPrototypeOf(this, LostContactError.prototype);
    }
}

/**
 * Starts the annotation job with the corrected exams form's options (field names match AnnotateForm).
 *
 * @param {FormData} options - The form's data, with its CSRF token.
 * @return {Promise<string>} The job's status URL, to follow it with followAnnotation().
 * @throws {HttpError} If the job couldn't be started (e.g. 409: the project is locked).
 */
export async function startAnnotation(options: FormData): Promise<string> {
    if (!urls) throw new ModuleUninitialized('annotate.ts', 'initAnnotate');

    const start = parseJson<AnnotateStartResponse>(await (await postForm(urls.annotate, {}, options)).text());
    if (!start) throw new Error('Annotate response was empty');
    return start.status_url;
}

/**
 * Follows an annotation job until it ends: just started, or still running when the page was loaded.
 *
 * @param {string} statusUrl - The job's status URL.
 * @param {(progress: string) => void} onProgress - Called with the job's progress text while it runs.
 * @return {Promise<AnnotateStatusResponse>} The job's final status ('done', or failed with its error).
 * @throws {LostContactError} After MAX_POLL_FAILURES failed status requests in a row.
 */
export async function followAnnotation(statusUrl: string, onProgress: (progress: string) => void): Promise<AnnotateStatusResponse> {
    let failures = 0;
    for (;;) {
        await sleep(POLL_INTERVAL_MS);

        let job: AnnotateStatusResponse;
        try {
            job = await getJson<AnnotateStatusResponse>(statusUrl);
            failures = 0;
        } catch (error) {
            console.error(error);
            if (++failures >= MAX_POLL_FAILURES) throw new LostContactError();
            continue;
        }

        if (job.status !== 'queued' && job.status !== 'running') return job;
        if (job.progress) onProgress(job.progress);
    }
}