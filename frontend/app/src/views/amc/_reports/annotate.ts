import { setAjaxInfoModalLocked } from '@examc/helpers/ajax-info-modal.ts';
import { byId, sleep } from '@examc/helpers/dom.ts';
import { parseJson, postText } from '@examc/helpers/http.ts';
import { ModuleUninitialized } from './errors.ts';
import { setInfoText, showInfo } from './info.ts';
import type { AnnotateStartResponse, AnnotateStatusResponse, AnnotateUrls } from './types.ts';

const POLL_INTERVAL_MS = 2000;
const MAX_POLL_FAILURES = 5;

let urls: AnnotateUrls | null = null;

/** Sets the API endpoints. Called by index.ts once the DOM has loaded. */
export function initAnnotate(endpoints: AnnotateUrls): void {
    urls = endpoints;
}

/**
 * Fetches the status of an annotation job.
 *
 * @param {string} statusUrl - The job's status URL, as returned by the annotate view.
 * @return {Promise<AnnotateStatusResponse>} The job status.
 */
async function fetchStatus(statusUrl: string): Promise<AnnotateStatusResponse> {
    const response = await fetch(statusUrl, { credentials: 'same-origin', headers: { Accept: 'application/json' } });
    if (!response.ok) throw new Error(`Annotation status request failed: ${response.status}`);

    const job = parseJson<AnnotateStatusResponse>(await response.text());
    if (!job) throw new Error('Annotation status response was empty');
    return job;
}

/**
 * Polls an annotation job until it ends, showing its progress in the info modal.
 * Gives up after MAX_POLL_FAILURES failed requests in a row.
 *
 * @param {string} statusUrl - The job's status URL.
 */
async function pollJob(statusUrl: string): Promise<void> {
    let failures = 0;

    for (;;) {
        await sleep(POLL_INTERVAL_MS);

        let job: AnnotateStatusResponse;
        try {
            job = await fetchStatus(statusUrl);
            failures = 0;
        } catch (error) {
            console.error(error);
            if (++failures >= MAX_POLL_FAILURES) {
                setAjaxInfoModalLocked(false);
                setInfoText('Lost contact with the server while annotating. Reload the page later to check the result.');
                return;
            }
            continue;
        }

        if (job.status === 'queued' || job.status === 'running') {
            setInfoText(job.progress || 'Still working…');
            continue;
        }

        setAjaxInfoModalLocked(false);
        setInfoText(job.status === 'done'
            ? (job.progress ? `Done! ${job.progress}` : 'Done!')
            : `Annotation failed: ${job.error || 'unknown error'}`);
        return;
    }
}

/** Starts the annotation job, then follows it in the (locked) info modal. */
export async function annotate(): Promise<void> {
    if (!urls) throw new ModuleUninitialized('annotate.ts', 'initAnnotate');

    showInfo("Generating annotated papers could take some time. We'll update this message when files are ready!");
    setAjaxInfoModalLocked(true);

    const singleFile = byId<HTMLInputElement>('annotate_one_all_student').checked;
    // Optional checkbox: not rendered for every exam.
    const withGradingScheme =
        document.querySelector<HTMLInputElement>('#annotate_with_grading_scheme')?.checked ?? false;

    let statusUrl: string;
    try {
        const start = parseJson<AnnotateStartResponse>(await postText(urls.annotate, {
            single_file: singleFile ? '1' : '0',
            add_grading_scheme_report: String(withGradingScheme),
        }));
        if (!start) throw new Error('Annotate response was empty');
        statusUrl = start.status_url;
    } catch (error) {
        console.error(error);
        setAjaxInfoModalLocked(false);
        setInfoText('Failed to start annotation job.');
        return;
    }

    await pollJob(statusUrl);
}