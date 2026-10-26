import { byId, requireData } from '@examc/helpers/dom.ts';

import { annotate, initAnnotate } from './annotate.ts';
import { generateResults, initResults } from './results.ts';
import { initSend, openSendDialog } from './send.ts';
import { LoadingModal } from '@examc/modals/loading.ts';
import { downloadFile } from '@examc/helpers/http.ts';

document.addEventListener('DOMContentLoaded', () => {
    const root = byId('amc-results');

    initResults({
        generate: requireData(root, 'generateResultsUrl'),
    });
    initAnnotate({
        annotate: requireData(root, 'annotateUrl'),
    });
    initSend({
        sendData: requireData(root, 'sendDataUrl'),
        send: requireData(root, 'sendUrl'),
    });

    // Generate results
    const generateResultsBtn = byId<HTMLButtonElement>('generate-results-btn');
    generateResultsBtn.addEventListener('click', () => {
        new LoadingModal(async () => {
            generateResultsBtn.disabled = true;
            await generateResults();
            generateResultsBtn.disabled = false;
        }).show();
    });

    // Generate corrected exams
    const annotateBtn = byId<HTMLButtonElement>('annotate-btn');
    annotateBtn.addEventListener('click', async () => {
        annotateBtn.disabled = true;
        await annotate();
        annotateBtn.disabled = false;
    });

    // Download (ZIP)
    const downloadZipBtn = byId<HTMLButtonElement>('download-zip-btn');
    downloadZipBtn.addEventListener('click', () => {
        const downloadZipUrl = requireData(root, 'downloadZipUrl');
        downloadZipBtn.disabled = true;

        new LoadingModal(() => downloadFile(downloadZipUrl, 'corrected-exams.zip')).result
            .catch((error: unknown) => {
                console.error('Downloading the corrected exams failed', error);
            })
            .finally(() => { downloadZipBtn.disabled = false; });
    });

    // Send annotated papers (the open button is only rendered when papers can be sent)
    document.getElementById('open-send-dialog-btn')?.addEventListener('click', () => void openSendDialog());
});