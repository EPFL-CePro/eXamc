import { byId, requireData } from '@examc/helpers/dom.ts';
import { annotate, initAnnotate } from './annotate.ts';
import { generateResults, initResults } from './results.ts';
import { initSend, onSendDialogShown, openSendDialog, sendAnnotatedPapers } from './send.ts';

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

    // Results
    const generateButton = byId<HTMLButtonElement>('generate-results-btn');
    generateButton.addEventListener('click', () => void generateResults(generateButton));

    // Annotated papers
    byId('annotate-btn').addEventListener('click', () => void annotate());

    // Send annotated papers (the open button is only rendered when papers can be sent)
    document.getElementById('open-send-dialog-btn')?.addEventListener('click', () => void openSendDialog());
    byId('send-annotated-papers-dialog').addEventListener('shown.bs.modal', () => void onSendDialogShown());
    byId('send-annotated-papers-btn').addEventListener('click', () => void sendAnnotatedPapers());
});