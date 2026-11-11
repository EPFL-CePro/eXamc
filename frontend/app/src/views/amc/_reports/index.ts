import { createAlert } from '@examc/helpers/alert';
import { byId, requireData } from '@examc/helpers/dom.ts';
import { downloadFile } from '@examc/helpers/http.ts';
import { showToast } from '@examc/helpers/toasts.ts';

import { followAnnotation, initAnnotate, LostContactError, startAnnotation } from './annotate.ts';
import { busyButton, progressAfter } from './busy.ts';
import { lockAmcView } from '../amc/lock.ts';
import { generateResults, initResults } from './results.ts';
import { initSend, openSendDialog, type SendResult } from './send.ts';

const TOAST_TITLE = 'Reports';

document.addEventListener('DOMContentLoaded', () => {
    const root = byId('amc-results');

    initResults({ generate: requireData(root, 'generateResultsUrl') });
    initAnnotate({ annotate: requireData(root, 'annotateUrl') });
    initSend({ sendData: requireData(root, 'sendDataUrl'), send: requireData(root, 'sendUrl') });

    // Checklist buttons: go to the tab to check (buttons rather than links, so the lock disables them)
    for (const button of root.querySelectorAll<HTMLButtonElement>('button[data-href]')) {
        button.addEventListener('click', () => window.location.assign(button.dataset['href'] ?? ''));
    }

    // -----------------------------------------------------------------------
    // Generate results: reloads the page, which then shows them
    // -----------------------------------------------------------------------

    const generateButton = byId<HTMLButtonElement>('generate-results-btn');
    const setGenerateBusy = busyButton(generateButton);
    const generateProgress = progressAfter(generateButton, 'Results generation progress');

    generateButton.addEventListener('click', async () => {
        setGenerateBusy('Generating…');
        lockAmcView(true, 'The results are being generated for this exam');
        generateProgress.show('Generating the results and statistics…');
        try {
            window.location.href = await generateResults(); // the AMC page, following the results import
        } catch (error) {
            console.error(error);
            showToast('The results couldn\'t be generated.', { error: true, title: TOAST_TITLE });
            generateProgress.hide();
            lockAmcView(false);
            setGenerateBusy(null);
        }
    });

    // -----------------------------------------------------------------------
    // Generate corrected exams: a background job, followed until it ends
    // -----------------------------------------------------------------------

    const annotateForm = byId<HTMLFormElement>('gen_annotated_papers_form');

    // The grading scheme details only apply with the grading schemes
    const gradingSchemeSwitch = document.querySelector<HTMLInputElement>('#annotate-with-grading-scheme');
    const gradingSchemeOptions = document.querySelector<HTMLFieldSetElement>('#annotate-grading-scheme-options');
    if (gradingSchemeSwitch && gradingSchemeOptions) {
        const sync = (): void => { gradingSchemeOptions.disabled = !gradingSchemeSwitch.checked; };
        gradingSchemeSwitch.addEventListener('change', sync);
        sync(); // the browser may have restored the switch's state
    }
    const annotateButton = byId<HTMLButtonElement>('annotate-btn');
    const setAnnotateBusy = busyButton(annotateButton);
    const annotateProgress = progressAfter(annotateForm, 'Corrected exams generation progress');

    /** Follows a running job, the whole AMC view locked, until it ends: reloads when it's done. */
    async function follow(statusUrl: string): Promise<void> {
        setAnnotateBusy('Generating…');
        lockAmcView(true, 'Corrected exams are being generated for this exam');
        annotateProgress.show('Generating the corrected exams… This can take a while.');
        try {
            const job = await followAnnotation(statusUrl,
                (text) => annotateProgress.show('Generating the corrected exams…', undefined, text));
            if (job.status === 'done') {
                window.location.reload(); // shows the download and send buttons, and the new date
                return;
            }
            showToast(`The corrected exams couldn't be generated: ${job.error || 'unknown error'}`,
                { error: true, title: TOAST_TITLE });
        } catch (error) {
            console.error(error);
            showToast(error instanceof LostContactError
                ? 'Lost contact with the server. The corrected exams may still be generated: reload the page later.'
                : 'The corrected exams generation couldn\'t be followed.',
                { error: true, title: TOAST_TITLE });
        }
        annotateProgress.hide();
        lockAmcView(false);
        setAnnotateBusy(null);
    }

    annotateButton.addEventListener('click', async () => {
        // Read before anything gets disabled: disabled fields are left out of the form data
        const options = new FormData(annotateForm);
        setAnnotateBusy('Starting…');
        let statusUrl: string;
        try {
            statusUrl = await startAnnotation(options);
        } catch (error) {
            console.error(error);
            showToast('The corrected exams generation couldn\'t be started.', { error: true, title: TOAST_TITLE });
            setAnnotateBusy(null);
            return;
        }
        await follow(statusUrl);
    });

    // A job started before this page was loaded (reload, other tab): follow it, view locked
    const runningJob = root.dataset['annotateJobStatusUrl'];
    if (runningJob) void follow(runningJob);

    // -----------------------------------------------------------------------
    // Download or send (only rendered once corrected exams exist)
    // -----------------------------------------------------------------------

    const actions = document.getElementById('annotated-papers-actions');
    if (!actions) return;
    const downloadButton = actions.querySelector<HTMLButtonElement>('#download-zip-btn');
    const sendButton = actions.querySelector<HTMLButtonElement>('#open-send-dialog-btn');

    const actionsProgress = progressAfter(actions, 'Corrected exams download progress');
    // The send result, under the buttons (replaced by the next one)
    const sendResult = document.createElement('div');
    sendResult.className = 'mt-3';
    sendResult.hidden = true;
    actions.after(sendResult);

    if (downloadButton) {
        const setDownloadBusy = busyButton(downloadButton);
        downloadButton.addEventListener('click', async () => {
            setDownloadBusy('Preparing…');
            actionsProgress.show('Preparing the ZIP file…');
            try {
                await downloadFile(requireData(root, 'downloadZipUrl'), 'corrected-exams.zip');
            } catch (error) {
                console.error('Downloading the corrected exams failed', error);
                showToast('The corrected exams couldn\'t be downloaded.', { error: true, title: TOAST_TITLE });
            } finally {
                actionsProgress.hide();
                setDownloadBusy(null);
            }
        });
    }

    /** The send result: counts, and the details as a list. Built with the DOM: the details come from the server. */
    function showSendResult({ sent, notSent, details }: SendResult): void {
        const content = document.createElement('div');
        content.append(`${sent} email${sent === 1 ? '' : 's'} sent, ${notSent} not sent.`);
        if (details.length) {
            const list = document.createElement('ul');
            list.className = 'mb-0 mt-2';
            list.append(...details.map((detail) => {
                const item = document.createElement('li');
                item.textContent = detail;
                return item;
            }));
            content.append(list);
        }
        sendResult.replaceChildren(createAlert({ alertType: notSent ? 'warning' : 'success', content }));
        sendResult.hidden = false;
    }

    if (sendButton) {
        const setSendBusy = busyButton(sendButton);
        sendButton.addEventListener('click', async () => {
            setSendBusy('Loading…');
            try {
                await openSendDialog(showSendResult);
            } catch (error) {
                console.warn(error);
                showToast('The students list couldn\'t be loaded.', { error: true, title: TOAST_TITLE });
            } finally {
                setSendBusy(null);
            }
        });
    }
});