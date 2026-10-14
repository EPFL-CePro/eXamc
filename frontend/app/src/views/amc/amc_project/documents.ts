import { sleep } from '@examc/helpers/dom.ts';
import { HttpError, postText } from '@examc/helpers/http.ts';
import { LoadingModal, LogModal } from '@examc/modals';

export interface DocumentsUrls {
    updateDocuments: string;
    layoutDetection: string;
    logFile: string;
    csrfToken: string;
}

/**
 * Updates the AMC documents, showing the AMC log file in the process modal while it runs.
 * Reloads the page once the documents are updated, so the tab shows the new state.
 *
 * @param {DocumentsUrls} options.urls - The URLs used.
 * @param {string} options.nbCopies - The number of copies to generate.
 */
export async function updateDocuments(options: { urls: DocumentsUrls; nbCopies: string }): Promise<void> {
    const { urls,  nbCopies } = options;

    const logPollIntervalMs = 250;
    const modal = new LogModal();

    modal.setTitle('Updating documents');
    modal.setOutput('');
    modal.show();

    const showLog = async (): Promise<void> => {
        try {
            modal.appendToOutput(await postText(urls.logFile, { csrfmiddlewaretoken: urls.csrfToken }));
        } catch {
            // The log file doesn't exist until AMC starts writing it.
        }
    };

    let running = true;

    const polling = (async () => {
        while (running) {
            await showLog();
            await sleep(logPollIntervalMs);
        }
    })();

    const stopPolling = async (): Promise<void> => {        
        running = false;
        await polling;
    };

    let result: string;

    try {
        result = await postText(urls.updateDocuments, { csrfmiddlewaretoken: urls.csrfToken, nb_copies: nbCopies });
    } catch (error) {
        await stopPolling();
        modal.appendToOutput(error instanceof HttpError
            ? `\n\nError occurred (${error.status})\n${error.body}\n`
            : `\n\nError occurred: the request was interrupted before a server response.\n${String(error)}\n`);
        return;
    }

    await stopPolling();
    await showLog();

    if (result.includes('ERR:')) {
        modal.appendToOutput(`\n\n ***** ERRORS DETECTED **** \n\n${result}`);
        return;
    }
    modal.appendToOutput('\n\n** UPDATE DOCUMENTS COMPLETED! **');    
}

/**
 * Runs the AMC layout detection and shows its result.
 *
 * @param {DocumentsUrls} urls - The URLs used.
 * @param {HTMLElement} message - The element showing the layout detection result.
 */
export async function runLayoutDetection(urls: DocumentsUrls, message: HTMLElement): Promise<void> {
    let result: string;
    try {
        result = await new LoadingModal(() => postText(urls.layoutDetection, { csrfmiddlewaretoken: urls.csrfToken })).result;
    } catch (error) {
        console.error(error);
        result = 'ERR: the layout detection request failed. Please try again.';
    }

    const failed = result.includes('ERR:');
    message.textContent = result;
    message.classList.toggle('alert-danger', failed);
    message.classList.toggle('alert-success', !failed);
}